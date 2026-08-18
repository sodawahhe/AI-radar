"""
GitHub Release 采集 —— 走 {repo}/releases.atom，不消耗 REST API 的 5000/h
额度（那份额度留给 collect_github.py 的技能雷达管道用，两条管道互不干扰）。

规格来源：daimonia-trends-radar 改造计划 v2 §三 §四

v1 曾经不加区分地取每仓库最近 5 个 release，导致同一仓库连续补丁版本号
刷屏（比如 v2.1.233 / v2.1.232 / v2.1.231 连发三条）。v2 加了实质性过滤：
只有语义版本升了 minor/major、且 changelog 有实质内容的 release 才收录，
每仓库每天最多 1 条。commits 采集整个删除——"合入某 PR"永远不构成一条
值得读的简报。
"""
from __future__ import annotations

import logging
import re

import feedparser
import requests

logger = logging.getLogger("collect_gh_events")

UA = "Mozilla/5.0 (compatible; ai-radar/1.0)"
REQUEST_TIMEOUT_S = 20

_SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")


def _parse_semver(tag: str) -> tuple[int, int, int] | None:
    m = _SEMVER_RE.match((tag or "").strip())
    if not m:
        return None
    return tuple(int(x) for x in m.groups())  # type: ignore[return-value]


def is_substantive_release(tag: str, body: str, cfg: dict) -> bool:
    """两道闸（第三道"每仓库每天最多 N 条"由调用方 collect_releases() 保证）：

    1. 语义版本可解析且 patch 位非零 → False（视为补丁流水，例如
       "v2.1.233" 相对 "v2.1.232" 只是补丁号递增）。解析不出语义版本的
       （llama.cpp 用的 "b10455" 这类构建号）不受此规则约束，直接放行，
       交给第 2 道判断。
    2. changelog 正文短于 min_changelog_chars → False（"fix typo"类，
       不构成一条值得读的简报）。

    两道闸是"与"的关系：一次补丁号递增但 changelog 很长的安全修复也会被
    第 1 道拦下——这是刻意的取舍，日报的目标是给 90 秒读完的大变化，不是
    穷尽每一次发布（改造计划 v2 已确认）。
    """
    if cfg.get("skip_patch_versions", True):
        version = _parse_semver(tag)
        if version is not None and version[2] != 0:
            return False
    min_chars = cfg.get("min_changelog_chars", 80)
    if len((body or "").strip()) < min_chars:
        return False
    return True


def _fetch_atom_entries(url: str) -> list:
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=REQUEST_TIMEOUT_S)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("拉取 %s 失败: %s，跳过", url, exc)
        return []
    return feedparser.parse(resp.content).entries


def collect_releases(repos: list[str], weight: float, cfg: dict) -> list[dict]:
    fetch_n = cfg.get("fetch_per_repo", 8)
    max_per_repo = cfg.get("max_per_repo_per_day", 1)
    items = []
    for repo in repos:
        entries = _fetch_atom_entries(f"https://github.com/{repo}/releases.atom")
        taken = 0
        for entry in entries[:fetch_n]:
            if taken >= max_per_repo:
                break
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            body = entry.get("summary") or ""
            if not title or not link:
                continue
            if not is_substantive_release(title, body, cfg):
                continue
            items.append({
                "title": f"{repo} 发布 {title}",
                "url": link,
                "source": "GitHub Release",
                "source_weight": weight,
                "published": entry.get("updated") or entry.get("published"),
                "summary_raw": body[:300],
                "category": "github",
            })
            taken += 1
    return items


def collect(sources_cfg: dict) -> list[dict]:
    cfg = sources_cfg.get("github_releases") or {}
    if not cfg:
        return []
    weight = cfg.get("weight", 0.9)
    items = collect_releases(cfg.get("watch", []), weight, cfg)
    logger.info("已拉取 GitHub releases: %d 条（实质性过滤后）", len(items))
    return items
