"""
summarize.py 的测试 —— 三层降级路径都必须产出非空 title_zh/body_zh，
邮件才能保证"必须发出去"（改造计划第一原则）。mock 掉 requests.post，
不真的连 DeepSeek。
"""
from __future__ import annotations

import json

import pytest
import requests

from src import summarize

LLM_CFG = {
    "provider": "deepseek",
    "model": "deepseek-v4-flash",
    "base_url": "https://api.deepseek.com/v1",
    "api_key_env": "DEEPSEEK_API_KEY",
    "timeout_s": 60,
    "max_output_tokens": 4000,
}


def make_items():
    return [
        {"title": "Some English Headline", "summary_raw": "Original raw summary text here.", "source": "TechCrunch"},
        {"title": "第二条候选标题", "summary_raw": "原始简介文本", "source": "36氪"},
    ]


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._json_data


def _deepseek_response(content: str):
    return FakeResponse({"choices": [{"message": {"content": content}}]})


def test_no_api_key_falls_back_to_raw_title(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    items, llm_used = summarize.summarize(make_items(), LLM_CFG)

    assert llm_used is False
    for it in items:
        assert it["title_zh"]
        assert it["title_zh"] == it["title"][:40]


def test_provider_none_falls_back_even_with_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
    cfg = dict(LLM_CFG, provider="none")
    items, llm_used = summarize.summarize(make_items(), cfg)
    assert llm_used is False
    assert all(it["title_zh"] for it in items)


def test_successful_call_uses_llm_output(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
    good_json = json.dumps(
        [
            {"i": 0, "title": "中文标题一", "body": "中文摘要正文一。"},
            {"i": 1, "title": "中文标题二", "body": "中文摘要正文二。"},
        ],
        ensure_ascii=False,
    )
    monkeypatch.setattr(summarize.requests, "post", lambda *a, **k: _deepseek_response(good_json))

    items, llm_used = summarize.summarize(make_items(), LLM_CFG)

    assert llm_used is True
    assert items[0]["title_zh"] == "中文标题一"
    assert items[1]["body_zh"] == "中文摘要正文二。"


def test_llm_output_strips_markdown_code_fence(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
    fenced = "```json\n" + json.dumps([{"i": 0, "title": "标题", "body": "正文。"}], ensure_ascii=False) + "\n```"
    monkeypatch.setattr(summarize.requests, "post", lambda *a, **k: _deepseek_response(fenced))

    items, llm_used = summarize.summarize([make_items()[0]], LLM_CFG)
    assert llm_used is True
    assert items[0]["title_zh"] == "标题"


def test_network_failure_falls_back(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")

    def raise_timeout(*a, **k):
        raise requests.Timeout("timed out")

    monkeypatch.setattr(summarize.requests, "post", raise_timeout)

    items, llm_used = summarize.summarize(make_items(), LLM_CFG)
    assert llm_used is False
    assert all(it["title_zh"] for it in items)


def test_invalid_json_falls_back(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
    monkeypatch.setattr(summarize.requests, "post", lambda *a, **k: _deepseek_response("not valid json {{{"))

    items, llm_used = summarize.summarize(make_items(), LLM_CFG)
    assert llm_used is False
    assert all(it["title_zh"] for it in items)


def test_partial_llm_result_falls_back_per_item(monkeypatch):
    """LLM 只返回了第 0 条的摘要（比如它漏了一条）—— 第 1 条应该单独降级，
    不能因为部分失败拖累整批。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
    partial_json = json.dumps([{"i": 0, "title": "标题零", "body": "正文零。"}], ensure_ascii=False)
    monkeypatch.setattr(summarize.requests, "post", lambda *a, **k: _deepseek_response(partial_json))

    items = make_items()
    result, llm_used = summarize.summarize(items, LLM_CFG)

    assert llm_used is True  # 调用本身成功了，只是有条目没覆盖到
    assert result[0]["title_zh"] == "标题零"
    assert result[1]["title_zh"] == result[1]["title"][:40]  # 降级
