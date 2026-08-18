"""
博客 RSS / Hacker News / V2EX 采集 —— 拉取原始条目，归一化成统一的 item 结构。

规格来源：daimonia-trends-radar 改造计划 v2 §三 §四

v1 曾经订阅 Google News + 36氪等二手媒体，翻车原因见改造计划 v2 Context——
转载聚合把泛财经噪声和搬运通稿一起带了进来。v2 只订阅一线从业者/实验室
博客，商业新闻不再有专属信源，靠 rank_news.reclassify_industry() 从其他
源的内容里按关键词筛出来。

每个源独立 try/except：一个源挂了只丢失那个源的条目，不影响其他源，
也不让整次运行失败——run_daily.py 只有"全部信源加起来是 0 条"才报错。
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import feedparser
import requests

logger = logging.getLogger("collect_feeds")

UA = "Mozilla/5.0 (compatible; ai-radar/1.0)"
REQUEST_TIMEOUT_S = 20
SUMMARY_TRUNCATE_CHARS = 300
POLITE_DELAY_S = 0.2


def _parsed_time_to_iso(entry) -> str | None:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc).isoformat()
    return None


def _entry_to_item(entry, source_name: str, source_weight: float, category: str) -> dict | None:
    title = (entry.get("title") or "").strip()
    link = (entry.get("link") or "").strip()
    if not title or not link:
        return None
    summary = entry.get("summary") or entry.get("description") or ""
    return {
        "title": title,
        "url": link,
        "source": source_name,
        "source_weight": source_weight,
        "published": _parsed_time_to_iso(entry),
        "summary_raw": summary[:SUMMARY_TRUNCATE_CHARS],
        "category": category,
    }


def _fetch_one_feed(name: str, url: str, weight: float, category: str) -> list[dict]:
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=REQUEST_TIMEOUT_S)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("拉取 %s 失败: %s，跳过该源", name, exc)
        return []
    parsed = feedparser.parse(resp.content)
    items = [item for entry in parsed.entries if (item := _entry_to_item(entry, name, weight, category))]
    logger.info("已拉取 %s: %d 条", name, len(items))
    return items


def collect_blogs(cfg: dict) -> list[dict]:
    """一线从业者/实验室博客——替代免费拿不到的 X 一线人物信号
    （改造计划 v2 已确认的决策）。"""
    items: list[dict] = []
    for src in cfg.get("blogs", []):
        items.extend(_fetch_one_feed(src["name"], src["url"], src.get("weight", 0.8), category="perspective"))
        time.sleep(POLITE_DELAY_S)
    return items


def collect_hackernews(cfg: dict) -> list[dict]:
    hn = cfg.get("hackernews") or {}
    if not hn:
        return []
    try:
        resp = requests.get(hn["url"], headers={"User-Agent": UA}, timeout=REQUEST_TIMEOUT_S)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("拉取 Hacker News 失败: %s，跳过该源", exc)
        return []
    min_points = hn.get("min_points", 200)
    weight = hn.get("weight", 0.8)
    items = []
    for hit in resp.json().get("hits", []):
        if hit.get("points", 0) < min_points:
            continue
        title = (hit.get("title") or "").strip()
        if not title:
            continue
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        items.append({
            "title": title,
            "url": url,
            "source": "Hacker News",
            "source_weight": weight,
            "published": hit.get("created_at"),
            "summary_raw": f"HN {hit.get('points', 0)} 分 · {hit.get('num_comments', 0)} 评论",
            "category": "community",
        })
    logger.info("已拉取 Hacker News: %d 条（>= %d 分）", len(items), min_points)
    return items


def collect_v2ex(cfg: dict) -> list[dict]:
    """V2EX 是综合程序员论坛，不过滤会灌进大量招聘/装机/生活帖——只收录
    标题命中 require_keywords 的帖子（改造计划 v2 §三）。"""
    v2 = cfg.get("v2ex") or {}
    if not v2:
        return []
    try:
        resp = requests.get(v2["url"], headers={"User-Agent": UA}, timeout=REQUEST_TIMEOUT_S)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("拉取 V2EX 失败: %s，跳过该源", exc)
        return []
    weight = v2.get("weight", 0.6)
    keywords = [k.lower() for k in v2.get("require_keywords", [])]
    parsed = feedparser.parse(resp.content)
    items = []
    for entry in parsed.entries:
        item = _entry_to_item(entry, "V2EX", weight, category="community")
        if not item:
            continue
        haystack = item["title"].lower()
        if keywords and not any(k in haystack for k in keywords):
            continue
        items.append(item)
    logger.info("已拉取 V2EX: %d 条（关键词过滤后）", len(items))
    return items


def collect(sources_cfg: dict) -> list[dict]:
    """采集入口：blogs + hackernews + v2ex。HF 由 collect_hf.collect() 处理，
    GitHub Release 由 collect_gh_events.collect() 处理。"""
    items: list[dict] = []
    items.extend(collect_blogs(sources_cfg))
    items.extend(collect_hackernews(sources_cfg))
    items.extend(collect_v2ex(sources_cfg))
    return items
