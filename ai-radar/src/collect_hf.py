"""
HuggingFace 模型生态采集 —— trending models / daily papers / trending datasets。

规格来源：daimonia-trends-radar 改造计划 v2 §三

三个端点都是免费 JSON API，无需 key。字段名来自 2026-08-18 实测响应
（不是猜的）：
  trending models:   list[{id, likes, trendingScore, downloads, tags,
                            pipeline_tag, createdAt}]
  daily_papers:       list[{title, summary, publishedAt, numComments,
                            paper: {id, ...}}]  —— 顶层字段与 paper.* 重复，
                            用顶层的更省事，只用 paper.id 拼 URL
  trending datasets:  list[{id, author, likes, trendingScore, downloads,
                            description, tags, lastModified}]

每个端点独立 try/except，一个挂了不影响另外两个。
"""
from __future__ import annotations

import logging

import requests

logger = logging.getLogger("collect_hf")

UA = "Mozilla/5.0 (compatible; ai-radar/1.0)"
REQUEST_TIMEOUT_S = 20
SUMMARY_TRUNCATE_CHARS = 300


def _get_json(url: str):
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=REQUEST_TIMEOUT_S)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.warning("拉取 %s 失败: %s，跳过", url, exc)
        return None
    except ValueError as exc:
        logger.warning("解析 %s 的 JSON 失败: %s，跳过", url, exc)
        return None


def collect_trending_models(url: str, weight: float) -> list[dict]:
    data = _get_json(url)
    if not data:
        return []
    items = []
    for m in data:
        model_id = m.get("id")
        if not model_id:
            continue
        tags = ", ".join(m.get("tags", [])[:6])
        summary = f"{m.get('pipeline_tag') or ''} · likes {m.get('likes', 0)} · downloads {m.get('downloads', 0)} · {tags}"
        items.append({
            "title": f"{model_id} 登上 HF 模型趋势榜",
            "url": f"https://huggingface.co/{model_id}",
            "source": "HF Trending Models",
            "source_weight": weight,
            # 不用 createdAt 当 published——那是模型创建时间，可能是几个月前，
            # 用它算新鲜度衰减会误伤"老模型突然火起来"这种真实的趋势信号。
            # HF 自己的 trendingScore 已经隐含了"最近有没有火"，留空交给
            # rank_news._hours_since() 的缺失时间戳默认值（48 小时，中性）。
            "published": None,
            "summary_raw": summary[:SUMMARY_TRUNCATE_CHARS],
            "category": "models",
        })
    logger.info("已拉取 HF trending models: %d 条", len(items))
    return items


def collect_daily_papers(url: str, weight: float) -> list[dict]:
    data = _get_json(url)
    if not data:
        return []
    items = []
    for p in data:
        title = (p.get("title") or "").strip()
        paper_id = (p.get("paper") or {}).get("id")
        if not title or not paper_id:
            continue
        summary = p.get("summary") or ""
        items.append({
            "title": f"HF 今日论文：{title}",
            "url": f"https://huggingface.co/papers/{paper_id}",
            "source": "HF Daily Papers",
            "source_weight": weight,
            "published": p.get("publishedAt"),
            "summary_raw": summary[:SUMMARY_TRUNCATE_CHARS],
            "category": "models",
        })
    logger.info("已拉取 HF daily papers: %d 条", len(items))
    return items


def collect_trending_datasets(url: str, weight: float) -> list[dict]:
    data = _get_json(url)
    if not data:
        return []
    items = []
    for d in data:
        dataset_id = d.get("id")
        if not dataset_id:
            continue
        summary = (d.get("description") or "").strip()
        items.append({
            "title": f"{dataset_id} 登上 HF 数据集趋势榜",
            "url": f"https://huggingface.co/datasets/{dataset_id}",
            "source": "HF Trending Datasets",
            "source_weight": weight,
            "published": None,  # lastModified 是数据文件修改时间，同上不用于新鲜度
            "summary_raw": summary[:SUMMARY_TRUNCATE_CHARS],
            "category": "models",
        })
    logger.info("已拉取 HF trending datasets: %d 条", len(items))
    return items


def collect(sources_cfg: dict) -> list[dict]:
    hf = sources_cfg.get("huggingface_api") or {}
    if not hf:
        return []
    weight = hf.get("weight", 1.0)
    items: list[dict] = []
    if hf.get("trending_models_url"):
        items.extend(collect_trending_models(hf["trending_models_url"], weight))
    if hf.get("daily_papers_url"):
        items.extend(collect_daily_papers(hf["daily_papers_url"], weight))
    if hf.get("trending_datasets_url"):
        items.extend(collect_trending_datasets(hf["trending_datasets_url"], weight))
    return items
