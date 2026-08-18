"""
collect_hf.py 的测试 —— mock 三个 HuggingFace API 响应，断言归一化成标准
item 结构。字段名取自 2026-08-18 对真实端点的实测响应（不是猜的）。

规格来源：daimonia-trends-radar 改造计划 v2 §四 §六
"""
from __future__ import annotations

import requests

from src import collect_hf

MODELS_RESPONSE = [
    {
        "id": "Qwen/Qwen3.8-27B",
        "likes": 10422,
        "trendingScore": 9955,
        "downloads": 267725,
        "tags": ["transformers", "safetensors", "conversational"],
        "pipeline_tag": "image-text-to-text",
        "createdAt": "2026-08-05T08:22:59.000Z",
    }
]

PAPERS_RESPONSE = [
    {
        "title": "LittleLearner: Language Models Under Pedagogically Controlled Knowledge Exposure",
        "summary": "Modern language models are trained on heterogeneous web-scale text corpora.",
        "publishedAt": "2026-08-12T20:00:00.000Z",
        "numComments": 1,
        "paper": {"id": "2608.13545"},
    }
]

DATASETS_RESPONSE = [
    {
        "id": "HuggingFaceFW/fineweb",
        "author": "HuggingFaceFW",
        "likes": 3223,
        "trendingScore": 68,
        "downloads": 401921,
        "description": "15 trillion tokens of the finest data the web has to offer",
        "lastModified": "2025-07-11T20:16:53.000Z",
    }
]


class FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._data


def test_collect_trending_models_normalizes_fields(monkeypatch):
    monkeypatch.setattr(collect_hf.requests, "get", lambda *a, **k: FakeResponse(MODELS_RESPONSE))
    items = collect_hf.collect_trending_models("https://fake", weight=1.0)

    assert len(items) == 1
    it = items[0]
    assert it["url"] == "https://huggingface.co/Qwen/Qwen3.8-27B"
    assert it["category"] == "models"
    assert it["source"] == "HF Trending Models"
    assert it["published"] is None  # createdAt 不用作 published，见模块文档


def test_collect_daily_papers_normalizes_fields(monkeypatch):
    monkeypatch.setattr(collect_hf.requests, "get", lambda *a, **k: FakeResponse(PAPERS_RESPONSE))
    items = collect_hf.collect_daily_papers("https://fake", weight=1.0)

    assert len(items) == 1
    it = items[0]
    assert it["url"] == "https://huggingface.co/papers/2608.13545"
    assert "LittleLearner" in it["title"]
    assert it["category"] == "models"
    assert it["published"] == "2026-08-12T20:00:00.000Z"  # 论文发布时间是真实新鲜度信号


def test_collect_trending_datasets_normalizes_fields(monkeypatch):
    monkeypatch.setattr(collect_hf.requests, "get", lambda *a, **k: FakeResponse(DATASETS_RESPONSE))
    items = collect_hf.collect_trending_datasets("https://fake", weight=1.0)

    assert len(items) == 1
    it = items[0]
    assert it["url"] == "https://huggingface.co/datasets/HuggingFaceFW/fineweb"
    assert it["category"] == "models"
    assert it["published"] is None


def test_missing_id_skips_item(monkeypatch):
    monkeypatch.setattr(collect_hf.requests, "get", lambda *a, **k: FakeResponse([{"likes": 5}]))
    assert collect_hf.collect_trending_models("https://fake", weight=1.0) == []


def test_network_failure_returns_empty_list(monkeypatch):
    def raise_error(*a, **k):
        raise requests.ConnectionError("boom")

    monkeypatch.setattr(collect_hf.requests, "get", raise_error)
    assert collect_hf.collect_trending_models("https://fake", weight=1.0) == []


def test_collect_entry_point_merges_all_three(monkeypatch):
    def fake_get(url, **k):
        if "models" in url:
            return FakeResponse(MODELS_RESPONSE)
        if "daily_papers" in url:
            return FakeResponse(PAPERS_RESPONSE)
        if "datasets" in url:
            return FakeResponse(DATASETS_RESPONSE)
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(collect_hf.requests, "get", fake_get)
    sources_cfg = {
        "huggingface_api": {
            "weight": 1.0,
            "trending_models_url": "https://fake/models",
            "daily_papers_url": "https://fake/daily_papers",
            "trending_datasets_url": "https://fake/datasets",
        }
    }
    items = collect_hf.collect(sources_cfg)
    assert len(items) == 3
    assert all(it["category"] == "models" for it in items)
