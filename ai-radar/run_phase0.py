"""
Phase 0 手动运行入口。规格：PROJECT_SPEC_V2.md §10、§14。

用法（PowerShell）：
    cd ai-radar
    pip install -r requirements.txt
    $env:GITHUB_TOKEN = "ghp_xxx"   # 可选但强烈建议，否则限速 60 次/小时
    python run_phase0.py

产出：reports/daily/{today}.md 与 data/snapshots/{today}.jsonl。

打开那份 markdown，亲眼判断：这份榜单是否比 github.com/trending 更有用？
这是 Phase 0 唯一的通过标准（PROJECT_SPEC_V2.md §10）。

本脚本不发邮件、不调用任何 LLM、不做厂商变动监控 —— 那些是 Phase 1/2 的范围。
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import render, score, store  # noqa: E402
from src.collect_github import collect  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("run_phase0")


def main() -> int:
    watchlist_path = ROOT / "config" / "watchlist.yaml"
    scoring_path = ROOT / "config" / "scoring.yaml"
    snapshots_dir = ROOT / "data" / "snapshots"
    reports_dir = ROOT / "reports" / "daily"

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.warning(
            "GITHUB_TOKEN 未设置 —— 未认证请求限速 60 次/小时，"
            "watchlist.yaml 里约 50 个 seed 仓库会很快耗尽额度。"
            "建议先在 GitHub 生成一个 fine-grained personal access token（无需任何写权限，"
            "public repo 只读即可），然后：$env:GITHUB_TOKEN = \"<token>\""
        )

    today = date.today()
    logger.info("开始采集（Phase 0：仅 watchlist.yaml 的 seeds，不抓 trending / topic 查询）...")

    records = collect(watchlist_path, scoring_path, snapshots_dir, token, today.isoformat())
    if not records:
        logger.error("采集结果为空，检查 GITHUB_TOKEN 和网络连接后重试")
        return 1

    snapshot_path = store.write_snapshot(snapshots_dir, today.isoformat(), records)
    logger.info("已写入快照: %s（%d 条记录）", snapshot_path, len(records))

    history_conn = store.build_memory_db(snapshots_dir)
    scored = score.score_records(records, history_conn, scoring_path, as_of=today)
    partitioned = score.partition(scored)

    report_path = render.write_report(partitioned, reports_dir, today)
    logger.info("已写入报告: %s", report_path)
    logger.info(
        "主榜 %d | 模板区 %d | 排除 %d | 待人工确认 %d",
        len(partitioned["main"]),
        len(partitioned["template"]),
        len(partitioned["excluded"]),
        len(partitioned["flagged"]),
    )
    logger.info("请打开 %s 亲眼评估：这份榜单是否比 github.com/trending 更有用？", report_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
