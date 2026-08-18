"""
run_daily.skill_radar_to_items() 的测试 —— 技能雷达主榜条目转成标准 item
结构，汇入资讯主候选池（改造计划 v2 §四 4）。
"""
from __future__ import annotations

from datetime import datetime, timezone

from run_daily import skill_radar_to_items

NOW = datetime(2026, 8, 19, 8, 0, tzinfo=timezone.utc)


def make_record(full_name, **overrides):
    record = {
        "full_name": full_name,
        "stars": 18200,
        "star_growth_7d": 2856,
        "fork_star_ratio": 0.12,
        "language": "Python",
        "description": "一个测试仓库",
    }
    record.update(overrides)
    return record


def test_converts_top_n_records_to_standard_items():
    records = [make_record(f"org/repo{i}") for i in range(10)]
    items = skill_radar_to_items(records, NOW, top_n=6)

    assert len(items) == 6
    it = items[0]
    assert it["title"] == "org/repo0"
    assert it["url"] == "https://github.com/org/repo0"
    assert it["category"] == "github"
    assert it["source"] == "GitHub Trending"
    assert "⭐18200" in it["summary_raw"]
    assert "+2856" in it["summary_raw"]


def test_items_are_cross_day_exempt():
    """趋势榜是每日快照，不该被跨天去重当旧闻过滤（见 normalize.py）。"""
    items = skill_radar_to_items([make_record("org/repo")], NOW, top_n=6)
    assert items[0]["cross_day_exempt"] is True


def test_published_is_now_not_repo_pushed_at():
    """星数快照是"此刻"的信号，不是一篇有独立发表时间的文章。"""
    items = skill_radar_to_items([make_record("org/repo")], NOW, top_n=6)
    assert items[0]["published"] == NOW.isoformat()


def test_respects_top_n_even_with_more_records_available():
    records = [make_record(f"org/repo{i}") for i in range(20)]
    items = skill_radar_to_items(records, NOW, top_n=3)
    assert len(items) == 3
