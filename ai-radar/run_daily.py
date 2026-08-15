"""
Phase 1 每日运行入口 —— GitHub Actions 定时任务实际调用的脚本。

规格来源：PROJECT_SPEC_V2.md §0 §6 §7 §10（Phase 1）

流程：采集 -> 打分 -> 写快照(JSONL) -> 写调试榜单(Markdown) -> 渲染邮件
(套用配额+静默日判断) -> 通过 Gmail SMTP 发送。

零 LLM（§2.1）：Phase 1 全程不调用任何 LLM，不做厂商变动监控（§5 是
Phase 2b 才接入的范围）。

快照/报告文件的 git 提交（状态持久化 + 60 天 cron 心跳，§7）在
.github/workflows/daily.yml 里用 shell 命令完成，不在这个脚本里 ——
本地手动跑这个脚本不会产生任何 git 操作。

必需的环境变量：
  GITHUB_TOKEN        - 用于认证 GitHub API（Actions 自动提供，无需手动设置）
  GMAIL_USER          - 发件/收件 Gmail 地址
  GMAIL_APP_PASSWORD  - Gmail 应用专用密码（不是登录密码）
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
from src.send import send_email  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("run_daily")


def main() -> int:
    watchlist_path = ROOT / "config" / "watchlist.yaml"
    scoring_path = ROOT / "config" / "scoring.yaml"
    snapshots_dir = ROOT / "data" / "snapshots"
    reports_dir = ROOT / "reports" / "daily"

    github_token = os.environ.get("GITHUB_TOKEN")
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")

    missing = [
        name
        for name, val in [
            ("GMAIL_USER", gmail_user),
            ("GMAIL_APP_PASSWORD", gmail_app_password),
        ]
        if not val
    ]
    if missing:
        logger.error("缺少必需的环境变量: %s —— 检查 GitHub Secrets 是否配置正确", ", ".join(missing))
        return 1
    if not github_token:
        logger.warning("GITHUB_TOKEN 未设置 —— 未认证请求限速 60 次/小时，可能不够用完整 watchlist")

    today = date.today()
    logger.info("开始采集...")
    records = collect(watchlist_path, scoring_path, snapshots_dir, github_token, today.isoformat())
    if not records:
        logger.error("采集结果为空，跳过本次运行（不发送邮件，避免发一封空内容的邮件）")
        return 1

    snapshot_path = store.write_snapshot(snapshots_dir, today.isoformat(), records)
    logger.info("已写入快照: %s（%d 条记录）", snapshot_path, len(records))

    history_conn = store.build_memory_db(snapshots_dir)
    scored = score.score_records(records, history_conn, scoring_path, as_of=today)
    partitioned = score.partition(scored)

    # 完整调试榜单照样保留，供你偶尔打开来看全貌，也在静默日邮件里被引用
    report_path = render.write_report(partitioned, reports_dir, today)
    logger.info("已写入调试榜单: %s", report_path)

    cfg = score.load_config(scoring_path)
    subject, body = render.render_email(partitioned, cfg["quotas"], cfg["silent_threshold"], today)
    logger.info("邮件主题: %s", subject)

    send_email(gmail_user, gmail_app_password, subject, body)
    logger.info("完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
