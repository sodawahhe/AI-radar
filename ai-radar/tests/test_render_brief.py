"""
render_brief.py 的测试 —— HTML/文本双版本渲染、5 分档、alert 标记、
完整榜单落盘。

规格来源：daimonia-trends-radar 改造计划 v2 §六

v2 把技能雷达提升为 GitHub 分档正文（不再有独立的 skill_radar 区块/参数），
分档从 v1 的 news/engineering/brief 三档改成 github/models/community/
perspective/industry 五档。
"""
from __future__ import annotations

from datetime import date

from src.render_brief import (
    group_by_category,
    render_html,
    render_subject,
    render_text,
    write_full_report,
)

STATS = {
    "raw_total": 486,
    "deduped_total": 231,
    "selected_total": 12,
    "sources_ok": 18,
    "sources_total": 19,
    "failed_sources": ["BAIR Berkeley"],
    "llm_status": "deepseek-v4-flash，用时 5.8s",
}


def make_item(i, category="community", title_zh=None, body_zh="正文摘要。", alert=None, dup_count=0):
    return {
        "title": f"raw title {i}",
        "title_zh": title_zh or f"中文标题{i}",
        "body_zh": body_zh,
        "url": f"https://example.com/{i}",
        "source": "Hacker News",
        "category": category,
        "score": 10 - i,
        "alert": alert,
        "dup_count": dup_count,
    }


def twelve_items():
    return (
        [make_item(i, "github") for i in range(4)]
        + [make_item(i, "models") for i in range(4, 7)]
        + [make_item(i, "community") for i in range(7, 10)]
        + [make_item(i, "perspective") for i in range(10, 12)]
    )


def test_group_by_category_preserves_fixed_order_and_score_desc():
    items = [
        make_item(0, "industry"),
        make_item(1, "github"),
        make_item(2, "models"),
    ]
    groups = group_by_category(items)
    assert list(groups.keys()) == ["github", "models", "community", "perspective", "industry"]
    assert [it["title"] for it in groups["github"]] == ["raw title 1"]


def test_html_contains_all_titles():
    items = twelve_items()
    groups = group_by_category(items)
    html = render_html(groups, stats=STATS, report_date=date(2026, 8, 19))
    for i in range(12):
        assert f"中文标题{i}" in html


def test_html_marks_alert_and_dup_count():
    items = [make_item(0, "industry", alert="涨价", dup_count=2)]
    groups = group_by_category(items)
    html = render_html(groups, stats=STATS, report_date=date(2026, 8, 19))
    assert "⚠️" in html
    assert "涨价" in html
    assert "3 处提及" in html  # dup_count=2 -> 代表自身 + 2 = 3 处


def test_text_version_contains_same_titles_as_html():
    items = twelve_items()
    groups = group_by_category(items)
    text = render_text(groups, stats=STATS, report_date=date(2026, 8, 19))
    for i in range(12):
        assert f"中文标题{i}" in text


def test_github_section_uses_github_label():
    groups = group_by_category([make_item(0, "github")])
    html = render_html(groups, stats=STATS, report_date=date(2026, 8, 19))
    assert "GitHub" in html


def test_subject_includes_date_and_github_headline():
    items = twelve_items()
    subject = render_subject(items, date(2026, 8, 19))
    assert "2026-08-19" in subject
    assert "AI 简报" in subject
    assert "中文标题0"[:16] in subject  # github 板块第一条（score 最高）


def test_subject_falls_back_to_generic_when_no_github_or_models():
    items = [make_item(0, "community"), make_item(1, "perspective")]
    subject = render_subject(items, date(2026, 8, 19))
    assert "今日简报" in subject


def test_write_full_report_marks_selected_items(tmp_path):
    all_items = twelve_items() + [make_item(12, "industry")]
    selected = twelve_items()  # 第 13 条（industry）未入选
    path = write_full_report(all_items, selected, tmp_path, date(2026, 8, 19))

    content = path.read_text(encoding="utf-8")
    assert "raw title 12" in content  # 未入选的也要出现在完整榜单
    lines = [l for l in content.splitlines() if "raw title 12" in l]
    assert "✅" not in lines[0]
