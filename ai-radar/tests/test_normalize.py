"""
normalize.py 的测试 —— 跨源去重（标题 Jaccard 相似度）与跨天去重（哈希查重）。

规格来源：daimonia-trends-radar 改造计划 §六
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from src import store
from src.normalize import (
    clean_text,
    dedup_cross_source,
    filter_cross_day,
    filter_stale,
    jaccard,
    normalize_url,
    title_hash,
)


def make_item(title, url="https://example.com/a", source_weight=1.0, **overrides):
    item = {"title": title, "url": url, "source_weight": source_weight}
    item.update(overrides)
    return item


def test_clean_text_strips_html_tags():
    dirty = '<h2>今日热点导览</h2><p>宇树科技未上市先疯抢 <a href="https://x.com">详情</a></p>'
    clean = clean_text(dirty)
    assert "<" not in clean
    assert ">" not in clean
    assert "今日热点导览" in clean
    assert "宇树科技未上市先疯抢" in clean


def test_clean_text_handles_empty_input():
    assert clean_text("") == ""
    assert clean_text(None) == ""


def test_filter_stale_drops_items_older_than_cutoff():
    now = datetime(2026, 8, 18, 8, 0, tzinfo=timezone.utc)
    fresh = {"title": "新", "published": (now - timedelta(hours=2)).isoformat()}
    stale = {"title": "旧", "published": (now - timedelta(hours=200)).isoformat()}
    kept = filter_stale([fresh, stale], now, max_age_hours=96)
    assert [it["title"] for it in kept] == ["新"]


def test_filter_stale_keeps_items_without_published_timestamp():
    now = datetime(2026, 8, 18, 8, 0, tzinfo=timezone.utc)
    no_ts = {"title": "无时间戳"}
    kept = filter_stale([no_ts], now, max_age_hours=96)
    assert len(kept) == 1


def test_normalize_url_strips_tracking_params():
    dirty = "https://example.com/article?utm_source=x&utm_campaign=y&id=42&ref=share#top"
    clean = normalize_url(dirty)
    assert "utm_source" not in clean
    assert "utm_campaign" not in clean
    assert "ref=" not in clean
    assert "id=42" in clean
    assert "#top" not in clean


def test_jaccard_similar_titles_score_high():
    a = "某支付公司据称以超70亿美元收购模型路由平台"
    b = "某支付公司以超70亿美元收购模型路由平台，据称交易已敲定"
    assert jaccard(a, b) >= 0.55


def test_jaccard_unrelated_titles_score_low():
    a = "某支付公司据称以超70亿美元收购模型路由平台"
    b = "杭州95后小伙，5亿买走硅谷城堡"
    assert jaccard(a, b) < 0.3


def test_dedup_cross_source_merges_similar_titles_and_counts_dup():
    """两条相似标题（同一事件的不同来源报道）应合并成一条，权重更高的
    那条作为代表保留，dup_count 记录"额外合并了几条"（不含代表自身）。"""
    items = [
        make_item("某支付公司据称以超70亿美元收购模型路由平台", source_weight=0.8, source="TechCrunch"),
        make_item("某支付公司以超70亿美元收购模型路由平台，据称交易已敲定", source_weight=1.0, source="彭博"),
    ]
    deduped = dedup_cross_source(items, threshold=0.55)

    assert len(deduped) == 1
    assert deduped[0]["source"] == "彭博"  # 高权重代表保留
    assert deduped[0]["dup_count"] == 1


def test_dedup_cross_source_never_merges_github_items():
    """回归测试：同一仓库连续版本号的 release 标题只差一两个字符
    （"v2.1.233" vs "v2.1.232"），Jaccard 相似度会超过阈值，但这是两个
    不同的真实 release，不是"同一事件的多家报道"——github 分类的
    条目不应该被跨源去重合并（见 dedup_cross_source 文档字符串）。"""
    items = [
        make_item("anthropics/claude-code 发布 v2.1.233", source_weight=0.9, category="github"),
        make_item("anthropics/claude-code 发布 v2.1.232", source_weight=0.9, category="github"),
        make_item("anthropics/claude-code 发布 v2.1.231", source_weight=0.9, category="github"),
    ]
    deduped = dedup_cross_source(items, threshold=0.55)
    assert len(deduped) == 3
    assert all(it["dup_count"] == 0 for it in deduped)


def test_dedup_cross_source_never_merges_models_items():
    """HF trending models/datasets 同理不参与跨源去重——单一权威结构化源，
    "N 家媒体报道"这个说法对它们没有意义。"""
    items = [
        make_item("openai/gpt-oss-120b 登上 HF 模型趋势榜", source_weight=1.0, category="models"),
        make_item("openai/gpt-oss-20b 登上 HF 模型趋势榜", source_weight=1.0, category="models"),
    ]
    deduped = dedup_cross_source(items, threshold=0.55)
    assert len(deduped) == 2
    assert all(it["dup_count"] == 0 for it in deduped)


def test_dedup_cross_source_keeps_unrelated_items_separate():
    items = [
        make_item("某支付公司收购模型路由平台", source_weight=1.0),
        make_item("杭州95后小伙，5亿买走硅谷城堡", source_weight=1.0),
    ]
    deduped = dedup_cross_source(items, threshold=0.55)
    assert len(deduped) == 2
    assert all(it["dup_count"] == 0 for it in deduped)


def test_filter_cross_day_drops_previously_seen_title(tmp_path):
    seen_dir = tmp_path / "seen"
    yesterday = date(2026, 8, 17)
    today = date(2026, 8, 18)

    old_title = "昨天已经推送过的新闻标题"
    store.write_seen(seen_dir, yesterday.isoformat(), [title_hash(old_title)])

    items = [
        make_item(old_title, url="https://a.com/1"),
        make_item("今天的新新闻标题", url="https://a.com/2"),
    ]
    kept = filter_cross_day(items, seen_dir, today, lookback_days=7)

    assert len(kept) == 1
    assert kept[0]["title"] == "今天的新新闻标题"


def test_filter_cross_day_keeps_cross_day_exempt_items(tmp_path):
    """技能雷达趋势榜条目（cross_day_exempt=True）是每日快照，不该被跨天
    去重当成旧闻过滤——同一仓库连续几天蝉联热门是正常情况，见
    run_daily.skill_radar_to_items()。"""
    seen_dir = tmp_path / "seen"
    yesterday = date(2026, 8, 17)
    today = date(2026, 8, 18)

    repo_title = "vllm-project/vllm"
    store.write_seen(seen_dir, yesterday.isoformat(), [title_hash(repo_title)])

    items = [make_item(repo_title, url="https://github.com/vllm-project/vllm", cross_day_exempt=True)]
    kept = filter_cross_day(items, seen_dir, today, lookback_days=7)

    assert len(kept) == 1


def test_filter_cross_day_respects_lookback_window(tmp_path):
    """超过 lookback_days 天的旧 seen 记录不再生效——同一条新闻在
    "冷却期"过后可以再次出现（比如一个月后旧闻重提）。"""
    seen_dir = tmp_path / "seen"
    old_title = "很久以前推送过的标题"
    ten_days_ago = date(2026, 8, 8)
    today = date(2026, 8, 18)
    store.write_seen(seen_dir, ten_days_ago.isoformat(), [title_hash(old_title)])

    items = [make_item(old_title, url="https://a.com/1")]
    kept = filter_cross_day(items, seen_dir, today, lookback_days=7)

    assert len(kept) == 1
