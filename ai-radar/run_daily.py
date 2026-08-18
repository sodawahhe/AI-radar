"""
每日运行入口 —— 资讯简报管道（v2：5 分档，GitHub 技能雷达升为一等公民）。

规格来源：daimonia-trends-radar 改造计划 v2

流程：
  采集   collect_feeds(blogs+HN+V2EX) + collect_gh_events(release，实质性过滤)
        + collect_hf(trending models/papers/datasets)
        + 技能雷达主榜前 N 条转成标准 item（skill_radar_to_items）
  行业重打标  reclassify_industry() —— 命中商业关键词的条目重归 industry 档
  归一化  normalize_all() —— 清洗/陈旧过滤/URL规范化/跨源去重/跨天去重
  打分    rank_news.score_all()
  配额选取 rank_news.quota_select() —— 5 分档 + 多样性上限，10-12 条
  摘要    summarize()  ← 唯一一次 LLM 调用，三层降级
  渲染发送 render_brief(HTML+text) -> send_email（永远发送，不再有静默日）
  落盘    seen 指纹 + 候选榜单 + 技能雷达完整榜单

DRY_RUN=1 时不真的发邮件，把渲染结果写到 out/preview.html / out/preview.txt。

必需环境变量：
  GMAIL_USER, GMAIL_APP_PASSWORD  —— 发信（DRY_RUN=1 时不需要）
  DEEPSEEK_API_KEY                —— 摘要，缺失时自动降级为原文（summarize.py）
  GITHUB_TOKEN                    —— 技能雷达管道用，可选，未认证限速更低
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import collect_feeds, collect_gh_events, collect_hf, normalize, rank_news, render_brief, store, summarize  # noqa: E402
from src import render as render_skill_radar  # noqa: E402
from src import score as score_mod  # noqa: E402
from src.collect_github import collect as collect_github  # noqa: E402
from src.send import send_email  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("run_daily")

# 自建 star 时间序列是这个系统唯一别处买不到的资产（PROJECT_SPEC_V2.md §1），
# v1 曾经把它压到邮件底部当附属品，v2 把主榜前几条转成标准 item 汇入主候选池，
# 池子比 github_max 配额（4）略宽，让 rank_news 的评分/去重有一点选择余地。
SKILL_RADAR_POOL_N = 6


def skill_radar_to_items(partitioned_main: list[dict], now: datetime, top_n: int) -> list[dict]:
    items = []
    for r in partitioned_main[:top_n]:
        full_name = r["full_name"]
        stars = r.get("stars", 0)
        growth = r.get("star_growth_7d", 0)
        items.append({
            "title": full_name,
            "url": f"https://github.com/{full_name}",
            "source": "GitHub Trending",
            "source_weight": 1.0,
            # 星数快照是"此刻"的信号，不是一篇有独立发表时间的文章——
            # 用 now 而不是仓库的 pushed_at，语义上更准确。
            "published": now.isoformat(),
            # 趋势榜是每日快照排行榜，不是一次性新闻——同一仓库连续蝉联
            # 热门是正常情况，不该被跨天去重当成"旧闻"过滤掉
            # （见 normalize.filter_cross_day() 文档字符串）。
            "cross_day_exempt": True,
            "summary_raw": (
                f"{r.get('description') or ''} · ⭐{stars}（近7天+{growth}）"
                f" · fork/star {r.get('fork_star_ratio')} · 语言 {r.get('language') or '—'}"
            ),
            "category": "github",
            "dup_count": 0,
        })
    return items


def run_news_pipeline(root: Path, today: date, now: datetime, skill_radar_items: list[dict]) -> tuple[dict, list[dict], dict]:
    sources_cfg_path = root / "config" / "sources.yaml"
    news_scoring_path = root / "config" / "news_scoring.yaml"
    llm_cfg_path = root / "config" / "llm.yaml"
    seen_dir = root / "data" / "seen"
    reports_dir = root / "reports" / "daily"

    with sources_cfg_path.open("r", encoding="utf-8") as f:
        sources_cfg = yaml.safe_load(f)
    news_cfg = rank_news.load_config(news_scoring_path)
    with llm_cfg_path.open("r", encoding="utf-8") as f:
        llm_cfg = yaml.safe_load(f)

    logger.info("开始采集资讯...")
    raw_items = collect_feeds.collect(sources_cfg)
    raw_items.extend(collect_gh_events.collect(sources_cfg))
    raw_items.extend(collect_hf.collect(sources_cfg))
    raw_items.extend(skill_radar_items)
    raw_total = len(raw_items)
    logger.info("原始条目: %d（含技能雷达 %d 条）", raw_total, len(skill_radar_items))

    raw_items = rank_news.reclassify_industry(raw_items, news_cfg.get("industry_keywords", {}))

    dedup_cfg = news_cfg.get("dedup", {})
    lookback_days = dedup_cfg.get("cross_day_lookback_days", 7)
    deduped = normalize.normalize_all(
        raw_items,
        seen_dir,
        now,
        cross_source_threshold=dedup_cfg.get("cross_source_jaccard_threshold", 0.55),
        cross_day_lookback_days=lookback_days,
        max_age_hours=news_cfg.get("max_age_hours", 96),
    )
    deduped_total = len(deduped)
    logger.info("去重后: %d", deduped_total)

    scored = rank_news.score_all(deduped, news_cfg, as_of=now)
    selected = rank_news.quota_select(scored, news_cfg)
    logger.info("入选: %d", len(selected))

    t0 = datetime.now(timezone.utc)
    selected, llm_used = summarize.summarize(selected, llm_cfg)
    elapsed = (datetime.now(timezone.utc) - t0).total_seconds()
    llm_status = (
        f"{llm_cfg.get('model')}，用时 {elapsed:.1f}s"
        if llm_used
        else "未启用/调用失败，已降级为原文摘要"
    )

    # 信源健康统计：只track blogs + HN + V2EX。github_releases（按仓库
    # Atom 端点）和 huggingface_api（三个独立 JSON 端点）粒度不同，且"今天
    # 没有实质性 release/没有新论文"是正常情况不是故障，不计入这个统计
    # （沿用 v1 已确认的设计：这个数字是给"持续挂了好几天"这种真故障用的）。
    all_source_names = {s["name"] for s in sources_cfg.get("blogs", [])} | {"Hacker News", "V2EX"}
    ok_sources = {it["source"] for it in raw_items if it["source"] in all_source_names}
    failed_sources = sorted(all_source_names - ok_sources)

    stats = {
        "raw_total": raw_total,
        "deduped_total": deduped_total,
        "selected_total": len(selected),
        "sources_ok": len(ok_sources),
        "sources_total": len(all_source_names),
        "failed_sources": failed_sources,
        "llm_status": llm_status,
    }

    render_brief.write_full_report(deduped, selected, reports_dir, today)
    seen_hashes = [normalize.title_hash(it["title"]) for it in selected if not it.get("cross_day_exempt")]
    store.write_seen(seen_dir, today.isoformat(), seen_hashes)
    store.prune_old_seen(seen_dir, today, keep_days=lookback_days)

    return render_brief.group_by_category(selected), selected, stats


def run_skill_radar(root: Path, today: date, now: datetime, github_token: str | None) -> list[dict]:
    """技能雷达采集+打分不变（collect_github.py / score.py 一行没改），
    只是把产出接到正确的位置：转成标准 item 汇入资讯主候选池，而不是
    单独放在邮件底部。独立 try/except——这条管道出错绝不能拖累资讯
    简报发送。"""
    try:
        watchlist_path = root / "config" / "watchlist.yaml"
        scoring_path = root / "config" / "scoring.yaml"
        snapshots_dir = root / "data" / "snapshots"
        reports_dir = root / "reports" / "daily"

        records = collect_github(watchlist_path, scoring_path, snapshots_dir, github_token, today.isoformat())
        if not records:
            logger.warning("技能雷达采集为空，GitHub 分档只有 Release 事件")
            return []
        store.write_snapshot(snapshots_dir, today.isoformat(), records)
        history_conn = store.build_memory_db(snapshots_dir)
        scored = score_mod.score_records(records, history_conn, scoring_path, as_of=today)
        partitioned = score_mod.partition(scored)
        # 完整排序榜单仍照旧写入 reports/daily/{date}.md（render.py 未改动），
        # 供偶尔人工翻阅技能雷达的完整打分明细。
        render_skill_radar.write_report(partitioned, reports_dir, today)
        return skill_radar_to_items(partitioned["main"], now, SKILL_RADAR_POOL_N)
    except Exception:
        logger.exception("技能雷达管道异常，GitHub 分档只有 Release 事件（不影响资讯简报发送）")
        return []


def main() -> int:
    dry_run = os.environ.get("DRY_RUN") == "1"
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
    github_token = os.environ.get("GITHUB_TOKEN")

    if not dry_run:
        missing = [n for n, v in [("GMAIL_USER", gmail_user), ("GMAIL_APP_PASSWORD", gmail_app_password)] if not v]
        if missing:
            logger.error("缺少必需的环境变量: %s —— 检查 GitHub Secrets 是否配置正确", ", ".join(missing))
            return 1
    if not github_token:
        logger.warning("GITHUB_TOKEN 未设置 —— 技能雷达管道未认证请求限速 60 次/小时")

    today = date.today()
    now = datetime.now(timezone.utc)

    skill_radar_items = run_skill_radar(ROOT, today, now, github_token)
    categories, selected, stats = run_news_pipeline(ROOT, today, now, skill_radar_items)
    if stats["raw_total"] == 0:
        logger.error("全部信源加起来是 0 条 —— 大概率是网络问题或全部源同时失效，跳过本次运行（不发空邮件）")
        return 1

    subject = render_brief.render_subject(selected, today)
    html_body = render_brief.render_html(categories, stats, today)
    text_body = render_brief.render_text(categories, stats, today)
    logger.info("邮件主题: %s", subject)

    if dry_run:
        out_dir = ROOT / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "preview.html").write_text(html_body, encoding="utf-8")
        (out_dir / "preview.txt").write_text(text_body, encoding="utf-8")
        logger.info("DRY_RUN=1，未发送邮件，预览已写入 out/preview.html 与 out/preview.txt")
        return 0

    send_email(gmail_user, gmail_app_password, subject, text_body, html_body=html_body)
    logger.info("完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
