"""
render_email() 与 send.build_message() 的测试 —— 纯函数，不需要真的连
SMTP 服务器，也不需要真的调 GitHub API。

规格来源：PROJECT_SPEC_V2.md §2.4（硬性配额）§6.1（静默日）§6.2（正常日）
"""
from __future__ import annotations

from datetime import date

import pytest

from src.render import render_email
from src.send import build_message


def make_scored_item(full_name, score, **overrides):
    item = {
        "full_name": full_name,
        "score": score,
        "stars": 1000,
        "forks": 100,
        "star_growth_7d": 50,
        "fork_star_ratio": 0.1,
        "language": "Python",
        "description": "A test repo",
        "integrity_action": None,
        "integrity_reasons": [],
    }
    item.update(overrides)
    return item


QUOTAS = {"skill_radar_max": 3, "watchlist_max": 3}
SILENT_THRESHOLD = 0.55


def test_silent_day_when_top_score_below_threshold():
    """主榜最高分低于阈值 -> 必须是静默日格式：主题以"无需关注"结尾，
    正文不列出任何具体条目（§6.1 不允许为了填满而降低阈值）。"""
    partitioned = {
        "main": [make_scored_item("a/b", score=0.30)],
        "template": [],
        "excluded": [],
        "flagged": [],
    }
    subject, body = render_email(partitioned, QUOTAS, SILENT_THRESHOLD, date(2026, 8, 16))

    assert subject == "AI Radar — 2026-08-16 — 无需关注"
    assert "今天没有需要你关注的进展" in body
    assert "a/b" not in body  # 静默日正文不应泄露具体条目名称


def test_empty_main_is_silent_day():
    """主榜为空（比如全部被完整性闸门排除）-> 同样是静默日，不能报错。"""
    partitioned = {"main": [], "template": [], "excluded": [], "flagged": []}
    subject, body = render_email(partitioned, QUOTAS, SILENT_THRESHOLD, date(2026, 8, 16))
    assert "无需关注" in subject
    assert "今天没有需要你关注的进展" in body


def test_normal_day_when_top_score_above_threshold():
    """主榜最高分达到阈值 -> 正常日格式，条目要出现在正文里。"""
    partitioned = {
        "main": [make_scored_item("cloudflare/computer", score=0.70)],
        "template": [],
        "excluded": [],
        "flagged": [],
    }
    subject, body = render_email(partitioned, QUOTAS, SILENT_THRESHOLD, date(2026, 8, 16))

    assert "无需关注" not in subject
    assert "cloudflare/computer" in body
    assert "👩‍💻" in body


def test_skill_radar_quota_is_enforced():
    """主榜有 5 条通过阈值的记录，但 skill_radar_max=3 -> 90秒版最多只能有
    3 条技能雷达条目，第 4、5 条应该落到"观察"区，不是被吞掉，也不是
    突破配额混进技能雷达区（§2.4 硬性配额，不是建议）。"""
    partitioned = {
        "main": [make_scored_item(f"org/repo{i}", score=0.9 - i * 0.05) for i in range(5)],
        "template": [],
        "excluded": [],
        "flagged": [],
    }
    subject, body = render_email(partitioned, QUOTAS, SILENT_THRESHOLD, date(2026, 8, 16))

    assert subject == "AI Radar — 2026-08-16 — 3 条技能雷达更新"
    for i in range(3):
        assert f"org/repo{i}" in body
    # repo3、repo4 应该出现在"观察"区（👀），而不是完全消失
    assert "org/repo3" in body
    assert "org/repo4" in body
    # 但不应该出现第 6 条以后的内容（本例只有 5 条，天然满足，无需额外断言）


def test_watchlist_quota_is_enforced():
    """再往后（超过 skill_radar_max + watchlist_max）的候选不应出现在邮件里
    ——它们进 backlog，不发送（§2.4）。"""
    partitioned = {
        "main": [make_scored_item(f"org/repo{i}", score=0.9 - i * 0.02) for i in range(10)],
        "template": [],
        "excluded": [],
        "flagged": [],
    }
    subject, body = render_email(partitioned, QUOTAS, SILENT_THRESHOLD, date(2026, 8, 16))

    # skill_radar_max=3 + watchlist_max=3 = 最多 6 条应该出现
    for i in range(6):
        assert f"org/repo{i}" in body
    for i in range(6, 10):
        assert f"org/repo{i}" not in body


def test_build_message_has_correct_headers():
    msg = build_message("me@gmail.com", "me@gmail.com", "Test Subject", "Test body")
    assert msg["Subject"] == "Test Subject"
    assert msg["From"] == "me@gmail.com"
    assert msg["To"] == "me@gmail.com"
    payload_bytes = msg.get_payload()[0].get_payload(decode=True)
    assert "Test body" in payload_bytes.decode("utf-8")
