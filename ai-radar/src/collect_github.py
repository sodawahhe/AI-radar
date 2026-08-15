"""
GitHub 采集器 —— 抓取 watchlist 仓库的基础字段，两段式补抓 adoption 数据。

规格来源：PROJECT_SPEC_V2.md §3.2 §3.3

Phase 0 范围：只使用 config/watchlist.yaml 中的 seeds 列表，不抓
trending 页、不做 topic 查询（那是 §3.2 里 Phase 1+ 才启用的来源，
watchlist.yaml 中已相应标注 enabled: false / 留空触发条件）。

两段式采集是为了满足 §3.3 的额度约束——"每次运行只调一次 /repos，
不调 /contributors 和 /releases。后两者只对进入 Top 20 的候选调用"：

  第一段：对全部 seeds 调 /repos，得到基础字段，写入内存记录。
  中间步骤：用 score.score_records() 做一次"粗排"（此时 adoption 字段
            全部是占位 None，排序主要由 momentum/freshness/relevance 决定），
            取粗排 Top 20。
  第二段：只对这 Top 20 补抓 /contributors 和 /releases，合并回记录。

返回的记录里，Top 20 之外的仓库 contributors/releases_90d 为 None——
这不是缺陷，是刻意的额度节省设计，score.py 已经据此正确处理（None 按 0
参与 adoption 公式，但 single_maintainer 完整性闸门只对有数据的仓库生效）。
"""
from __future__ import annotations

import logging
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import requests
import yaml

from src.score import score_records
from src.store import build_memory_db

logger = logging.getLogger("collect_github")

GITHUB_API = "https://api.github.com"
TOP_N_FOR_ADOPTION_FETCH = 20
RELEASES_LOOKBACK_DAYS = 90
REQUEST_TIMEOUT_S = 15
POLITE_DELAY_S = 0.1  # 认证后 5000/h 额度下无需更保守的限速


class GitHubClient:
    """薄封装：认证头 + 超时 + 命中 429/403 限速时的一次性等待重试。
    不做缓存 —— 缓存/持久化是 store.py 的职责，这里只负责单次请求。"""

    def __init__(self, token: str | None = None, session: requests.Session | None = None):
        self.session = session or requests.Session()
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ai-radar-phase0",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.session.headers.update(headers)

    def _get(self, path: str, params: dict | None = None) -> requests.Response:
        url = f"{GITHUB_API}{path}"
        resp = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT_S)
        if resp.status_code == 403 and resp.headers.get("X-RateLimit-Remaining") == "0":
            reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait_s = max(reset - time.time(), 1)
            logger.warning("命中 GitHub 速率限制，等待 %.0f 秒后重试一次", wait_s)
            time.sleep(min(wait_s, 120))
            resp = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT_S)
        return resp

    def get_repo(self, full_name: str) -> dict | None:
        resp = self._get(f"/repos/{full_name}")
        if resp.status_code == 404:
            logger.warning("仓库不存在或已改名/删除，跳过: %s", full_name)
            return None
        if resp.status_code != 200:
            logger.warning("拉取 %s 失败（HTTP %d），跳过", full_name, resp.status_code)
            return None
        return resp.json()

    def get_contributors_count(self, full_name: str) -> int:
        """通过 Link header 的 last-page 参数近似取贡献者总数，避免翻全部页。
        无法解析（≤1 页）时退化为当页结果长度。贡献者数只用于 log1p，
        近似误差对最终排序影响可忽略。"""
        try:
            resp = self._get(f"/repos/{full_name}/contributors", params={"per_page": 1, "anon": "true"})
        except requests.RequestException as exc:
            logger.warning("拉取 %s 贡献者数失败: %s", full_name, exc)
            return 0
        if resp.status_code != 200:
            return 0
        link = resp.headers.get("Link", "")
        if 'rel="last"' in link:
            for part in link.split(","):
                if 'rel="last"' in part:
                    url = part.split(";")[0].strip().strip("<>")
                    qs = url.split("page=")[-1]
                    try:
                        return int(qs.split("&")[0])
                    except ValueError:
                        pass
        try:
            return len(resp.json())
        except ValueError:
            return 0

    def get_releases_90d_count(self, full_name: str) -> int:
        try:
            resp = self._get(f"/repos/{full_name}/releases", params={"per_page": 30})
        except requests.RequestException as exc:
            logger.warning("拉取 %s release 列表失败: %s", full_name, exc)
            return 0
        if resp.status_code != 200:
            return 0
        cutoff = datetime.now(timezone.utc).timestamp() - RELEASES_LOOKBACK_DAYS * 86400
        count = 0
        for rel in resp.json():
            published = rel.get("published_at")
            if not published:
                continue
            try:
                ts = datetime.fromisoformat(published.replace("Z", "+00:00")).timestamp()
            except ValueError:
                continue
            if ts >= cutoff:
                count += 1
        return count


def repo_to_record(repo: dict, snapshot_date: str) -> dict:
    return {
        "full_name": repo["full_name"],
        "stars": repo.get("stargazers_count", 0),
        "forks": repo.get("forks_count", 0),
        "open_issues": repo.get("open_issues_count", 0),
        "watchers": repo.get("subscribers_count", repo.get("watchers_count", 0)),
        "pushed_at": repo.get("pushed_at"),
        "created_at": repo.get("created_at"),
        "license": (repo.get("license") or {}).get("spdx_id"),
        "language": repo.get("language"),
        "topics": repo.get("topics", []),
        "description": repo.get("description") or "",
        "snapshot_date": snapshot_date,
        # adoption 字段：默认占位 None，只对粗排 Top 20 补抓真实值（模块文档）
        "contributors": None,
        "releases_90d": None,
    }


def load_seeds(watchlist_path: Path) -> list[str]:
    with watchlist_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg.get("seeds", [])


def collect(
    watchlist_path: Path,
    scoring_path: Path,
    snapshots_dir: Path,
    token: str | None,
    snapshot_date: str | None = None,
    top_n_for_adoption: int = TOP_N_FOR_ADOPTION_FETCH,
) -> list[dict]:
    """Phase 0 采集入口：只跑 seeds。返回最终记录列表（粗排 Top N 已补齐
    adoption 字段），调用方负责写快照（见 run_phase0.py）。

    top_n_for_adoption 默认等于 TOP_N_FOR_ADOPTION_FETCH（§3.3 规定的 20）。
    调低这个参数只应在"没有 GITHUB_TOKEN、要在未认证 60 次/小时额度内
    一次跑完"这种一次性场景下使用，不应作为长期默认值 —— 一旦接入
    GITHUB_TOKEN（认证后 5000 次/小时），应恢复使用默认的 20。
    """
    snapshot_date = snapshot_date or date.today().isoformat()
    seeds = load_seeds(watchlist_path)
    client = GitHubClient(token=token)

    records: list[dict] = []
    for full_name in seeds:
        repo = client.get_repo(full_name)
        if repo is None:
            continue
        records.append(repo_to_record(repo, snapshot_date))
        time.sleep(POLITE_DELAY_S)

    if not records:
        logger.error("采集到 0 条记录 —— 检查 GITHUB_TOKEN 或 watchlist 中的仓库名是否有效")
        return []

    logger.info("已拉取 %d/%d 个 seed 仓库的基础字段", len(records), len(seeds))

    # 粗排：用已有历史（可能为空）计算 momentum，adoption 字段全部是占位 None，
    # 排序主要由 momentum/freshness/relevance 决定，用于圈定补抓 adoption 的 Top 20。
    history_conn = build_memory_db(snapshots_dir)
    rough_scored = score_records(records, history_conn, config_path=scoring_path, as_of=date.fromisoformat(snapshot_date))
    rough_scored.sort(key=lambda r: r["score"], reverse=True)
    top_names = {r["full_name"] for r in rough_scored[:top_n_for_adoption]}

    logger.info("补抓 Top %d 候选的 contributors / releases: %s", len(top_names), ", ".join(sorted(top_names)))

    by_name = {r["full_name"]: r for r in records}
    for full_name in top_names:
        by_name[full_name]["contributors"] = client.get_contributors_count(full_name)
        time.sleep(POLITE_DELAY_S)
        by_name[full_name]["releases_90d"] = client.get_releases_90d_count(full_name)
        time.sleep(POLITE_DELAY_S)

    return list(by_name.values())


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from src import store

    watchlist_path = _ROOT / "config" / "watchlist.yaml"
    scoring_path = _ROOT / "config" / "scoring.yaml"
    snapshots_dir = _ROOT / "data" / "snapshots"

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.warning("GITHUB_TOKEN 未设置 —— 未认证请求限速 60 次/小时，可能不够用完整 seeds 列表")

    snapshot_date = date.today().isoformat()
    records = collect(watchlist_path, scoring_path, snapshots_dir, token, snapshot_date)
    if not records:
        return 1

    path = store.write_snapshot(snapshots_dir, snapshot_date, records)
    logger.info("已写入 %d 条记录到 %s", len(records), path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
