"""
清洗 + URL 规范化 + 跨源去重（标题 Jaccard 相似度）+ 跨天去重（哈希查重）。

规格来源：daimonia-trends-radar 改造计划 §四

几件事都在这里做，任何一件缺失都会导致简报质量下降：
  1. clean_text()          —— 剥掉 RSS description 里的 HTML 标签，
                               不清洗会导致 <a href=...> 这类标签直接
                               泄漏进降级摘要和喂给 LLM 的文本
  2. filter_stale()        —— 丢弃发布时间太旧的条目。实测发现
                               HuggingFace/OpenAI 博客 RSS 会返回整个历史
                               归档（800+ 条陈年文章），不过滤会把跨源去重
                               的候选池撑到几千条，O(n^2) 比较明显变慢，
                               而且陈年旧闻本就不该出现在"今日"简报里
  3. normalize_url()       —— 剥掉跟踪参数，供去重和渲染共用一份干净链接
  4. dedup_cross_source()  —— 同一事件被多家媒体报道时合并成一条，记录 dup_count
  5. filter_cross_day()    —— 昨天已经发过的标题今天不再发（读 data/seen/，见 store.py）

没有第 5 步，同一条新闻会连发三天——这是资讯推送最常见的翻车点。
"""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from src import store

_TRACKING_PARAM_PREFIXES = ("utm_", "spm", "from")
_TRACKING_PARAM_EXACT = {"ref", "ref_src", "igshid"}


def clean_text(html_or_text: str) -> str:
    """剥掉 HTML 标签，只留纯文本。RSS 的 summary/description 字段几乎总是
    HTML（哪怕只是一段纯文字，也常常包在 <p> 里），不清洗会让 <a href=...>
    这类标签原样出现在降级摘要和 LLM 输入里。"""
    if not html_or_text:
        return ""
    text = BeautifulSoup(html_or_text, "html.parser").get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def filter_stale(items: list[dict], now: datetime, max_age_hours: float = 96) -> list[dict]:
    """丢弃发布时间早于 max_age_hours 的条目。没有 published 时间戳的条目
    保留——缺失时间戳不代表陈旧（呼应 rank_news.py 对同一情况的处理）。"""
    kept = []
    for it in items:
        published = it.get("published")
        if not published:
            kept.append(it)
            continue
        try:
            dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError:
            kept.append(it)
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_hours = (now - dt.astimezone(timezone.utc)).total_seconds() / 3600.0
        if age_hours <= max_age_hours:
            kept.append(it)
    return kept


def normalize_url(url: str) -> str:
    """剥离跟踪参数与 fragment。"""
    if not url:
        return url
    parts = urlsplit(url)
    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAM_EXACT
        and not any(k.lower().startswith(p) for p in _TRACKING_PARAM_PREFIXES)
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), ""))


def _normalize_title_for_compare(title: str) -> str:
    """去空白、去标点，只留中英文字符与数字，转小写——供哈希和
    n-gram 比较共用，保证同一标题在两处产出一致的规范化结果。"""
    title = re.sub(r"\s+", "", title or "")
    title = re.sub(r"[^\w一-鿿]", "", title)
    return title.lower()


def title_hash(title: str) -> str:
    return hashlib.sha1(_normalize_title_for_compare(title).encode("utf-8")).hexdigest()


def _char_ngrams(text: str, n: int = 2) -> set[str]:
    """字符级 n-gram —— 中英文混合标题都能用同一套逻辑比较，
    不引入 jieba 分词依赖（改造计划附注：判断二）。"""
    cleaned = _normalize_title_for_compare(text)
    if len(cleaned) < n:
        return {cleaned} if cleaned else set()
    return {cleaned[i : i + n] for i in range(len(cleaned) - n + 1)}


def jaccard(a: str, b: str) -> float:
    set_a, set_b = _char_ngrams(a), _char_ngrams(b)
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union else 0.0


DEDUP_EXEMPT_CATEGORIES = {"github", "models"}


def dedup_cross_source(items: list[dict], threshold: float = 0.55) -> list[dict]:
    """按 source_weight 降序贪心聚类：同一事件的多条报道合并成一条，
    保留 source_weight 最高的那条作为代表，dup_count 记录合并了几条
    （dup_count 之后会在 rank_news.py 里转成打分加权，也是简报里
    "N 家媒体报道"的数据来源）。

    category 属于 DEDUP_EXEMPT_CATEGORIES（github / models）的条目不参与
    聚类，原样直通——这两类内容来自单一权威结构化源（GitHub Release API、
    HuggingFace API），"N 家媒体报道"这个说法对它们没有意义，而且实测发现
    同一仓库连续几个版本号相近的 release 标题（"v2.1.233" vs "v2.1.232"）
    只差一两个字符，会被 Jaccard 误判成"同一事件的多家报道"合并掉——那是
    两个不同的真实 release。"同一事件多方报道"这个概念只对新闻/社区/
    一线视角这类叙事性内容成立。

    候选量级是几百条，O(n^2) 标题两两比较足够快，不需要更复杂的索引。
    """
    dedup_eligible = [it for it in items if it.get("category") not in DEDUP_EXEMPT_CATEGORIES]
    passthrough = [it for it in items if it.get("category") in DEDUP_EXEMPT_CATEGORIES]
    for it in passthrough:
        it.setdefault("dup_count", 0)

    ordered = sorted(dedup_eligible, key=lambda it: it.get("source_weight", 0.0), reverse=True)
    kept: list[dict] = []
    for item in ordered:
        item.setdefault("dup_count", 0)
        merged = False
        for rep in kept:
            if jaccard(item["title"], rep["title"]) >= threshold:
                rep["dup_count"] += 1
                merged = True
                break
        if not merged:
            kept.append(item)
    return kept + passthrough


def filter_cross_day(
    items: list[dict],
    seen_dir: Path,
    as_of: date,
    lookback_days: int = 7,
) -> list[dict]:
    """丢弃最近 lookback_days 天已经推送过的标题（按哈希比对，见 store.py
    read_recent_seen_hashes()）。

    cross_day_exempt=True 的条目不受此过滤——技能雷达的"趋势榜"条目
    （run_daily.skill_radar_to_items()，source="GitHub Trending"）本质是
    每日快照排行榜，不是一次性新闻：同一个仓库连续几天蝉联热门是正常且
    应该继续报道的情况（类似"今天的股价"每天都报，不因为昨天也报过就不
    报了），标题固定为 full_name，不跨天去重会导致它在连续霸榜时被误判
    成"旧闻"而消失。真正的一次性新闻（release 事件、博客文章）不受影响，
    仍然正常跨天去重。"""
    seen = store.read_recent_seen_hashes(seen_dir, as_of, lookback_days)
    return [it for it in items if it.get("cross_day_exempt") or title_hash(it["title"]) not in seen]


def normalize_all(
    items: list[dict],
    seen_dir: Path,
    now: datetime,
    cross_source_threshold: float = 0.55,
    cross_day_lookback_days: int = 7,
    max_age_hours: float = 96,
) -> list[dict]:
    """归一化入口：清洗 -> 过滤陈旧条目 -> URL 规范化 -> 跨源去重 -> 跨天去重。
    顺序固定：
      - 陈旧过滤要最先跑，把候选池砍到几百条量级，后面 O(n^2) 的跨源去重
        才不会因为某个博客 RSS 返回了整个历史归档而变慢（实测 HuggingFace/
        OpenAI 博客 feed 会返回 800+ 条陈年文章）
      - 跨源去重要在跨天去重之前，这样合并出的代表条目的 dup_count 才会
        参与后续排序；跨天去重放最后，因为它是最终过滤，过滤掉的条目
        不该再影响 dup_count 统计
    """
    for it in items:
        it["summary_raw"] = clean_text(it.get("summary_raw", ""))[:300]
        it["url"] = normalize_url(it.get("url", ""))
    fresh = filter_stale(items, now, max_age_hours=max_age_hours)
    deduped = dedup_cross_source(fresh, threshold=cross_source_threshold)
    return filter_cross_day(deduped, seen_dir, now.date(), lookback_days=cross_day_lookback_days)
