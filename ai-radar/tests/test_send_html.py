"""
send.build_message() 的 HTML alternative 测试。

规格来源：daimonia-trends-radar 改造计划 §四 7
"""
from __future__ import annotations

from src.send import build_message


def test_build_message_without_html_stays_plain_text_only():
    msg = build_message("me@gmail.com", "me@gmail.com", "Subject", "Plain body")
    payloads = msg.get_payload()
    assert len(payloads) == 1
    assert payloads[0].get_content_type() == "text/plain"


def test_build_message_with_html_attaches_both_parts_html_last():
    msg = build_message("me@gmail.com", "me@gmail.com", "Subject", "Plain body", html_body="<p>HTML body</p>")
    payloads = msg.get_payload()
    assert len(payloads) == 2
    assert payloads[0].get_content_type() == "text/plain"
    assert payloads[1].get_content_type() == "text/html"  # 后 attach = 客户端首选展示版本

    plain_bytes = payloads[0].get_payload(decode=True).decode("utf-8")
    html_bytes = payloads[1].get_payload(decode=True).decode("utf-8")
    assert "Plain body" in plain_bytes
    assert "<p>HTML body</p>" in html_bytes
