"""
零 LLM 打分 + 行业分类重打标 + 配额选取（v2：5 分档 + 多样性上限）。

规格来源：daimonia-trends-radar 改造计划 v2 §四

score = source_weight
      × 0.5 ** (hours_since_published / half_life_hours)
      × (1 + 0.3 × min(dup_count, 3))
      + substance_score（technical 实质关键词命中，正向）
      + noise_score（泛财经噪声命中，负向）
      + entity_score（entity_bonus 表命中）

配额是上限也是下限——每个分档先保证至少 1 条（industry 除外，它没有
下限），剩余名额按分数从高到低跨分档补满到 total_max；如果连 total_min
都凑不够，放宽多样性上限继续补（沿用 PROJECT_SPEC_V2.md §2.4 硬性配额
原则）。
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

CATEGORIES = ["github", "models", "community", "perspective", "industry"]

_GITHUB_REPO_RE = re.compile(r"^https://github\.com/([^/]+/[^/]+)")


def load_config(news_scoring_path: Path) -> dict:
    with Path(news_scoring_path).open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _hours_since(published_iso: str | None, as_of: datetime) -> float:
    """published 缺失或无法解析时视为 48 小时前——足够旧，避免时间戳
    解析失败的条目意外拿到"刚发布"的高分，但又不会被直接判 0 分排除。
    HF trending models/datasets 故意不带 published（见 collect_hf.py），
    也走这个中性默认值。"""
    if not published_iso:
        return 48.0
    try:
        dt = datetime.fromisoformat(published_iso.replace("Z", "+00:00"))
    except ValueError:
        return 48.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = as_of - dt.astimezone(timezone.utc)
    return max(delta.total_seconds() / 3600.0, 0.0)


def _keyword_score(text: str, keyword_cfg: dict) -> float:
    haystack = (text or "").lower()
    weight = keyword_cfg.get("weight", 0.0)
    return weight * sum(1 for term in keyword_cfg.get("terms", []) if term.lower() in haystack)


def _matched_alert(text: str, alert_cfg: dict) -> str | None:
    haystack = (text or "").lower()
    for term in alert_cfg.get("terms", []):
        if term.lower() in haystack:
            return term
    return None


def _matches_any(text: str, terms: list[str]) -> bool:
    haystack = (text or "").lower()
    return any(term.lower() in haystack for term in terms)


def reclassify_industry(items: list[dict], industry_cfg: dict) -> list[dict]:
    """把命中 industry_keywords 的条目重新打上 category="industry"，覆盖
    原分类。industry 档没有专属信源（改造计划 v2 §三），完全靠这一步从
    community/perspective 的内容里筛出来。

    category == "github" 的条目不参与重打标——GitHub release 标题几乎不
    会命中"收购/融资/IPO"这类词，即使偶然命中也不该被移出 GitHub 板块
    （它首先是一条技术发布，不是一条商业新闻）。"""
    terms = industry_cfg.get("terms", [])
    if not terms:
        return items
    for it in items:
        if it.get("category") == "github":
            continue
        text = f"{it.get('title', '')} {it.get('summary_raw', '')}"
        if _matches_any(text, terms):
            it["category"] = "industry"
    return items


def score_item(item: dict, cfg: dict, as_of: datetime) -> dict:
    half_life = cfg.get("freshness_half_life_hours", 18)
    hours = _hours_since(item.get("published"), as_of)
    freshness = 0.5 ** (hours / half_life)
    dup_boost = 1 + 0.3 * min(item.get("dup_count", 0), 3)
    base = item.get("source_weight", 0.5) * freshness * dup_boost

    text = f"{item.get('title', '')} {item.get('summary_raw', '')}"
    substance_score = _keyword_score(text, cfg.get("substance_keywords", {}))
    noise_score = _keyword_score(text, cfg.get("noise_keywords", {}))
    entity_score = _keyword_score(text, cfg.get("entity_bonus", {}))

    item["score"] = base + substance_score + noise_score + entity_score
    item["alert"] = _matched_alert(text, cfg.get("alert_keywords", {}))
    return item


def score_all(items: list[dict], cfg: dict, as_of: datetime | None = None) -> list[dict]:
    as_of = as_of or datetime.now(timezone.utc)
    return [score_item(it, cfg, as_of) for it in items]


def _extract_repo(item: dict) -> str | None:
    m = _GITHUB_REPO_RE.match(item.get("url", ""))
    return m.group(1) if m else None


def quota_select(items: list[dict], cfg: dict) -> list[dict]:
    """两轮选取 + 多样性上限：

    第一轮：每个有下限的分档（github/models/community/perspective）先保证
    至少 1 条，保证每天的邮件都覆盖全部视角，不会因为某个分档当天分数普遍
    偏低而完全消失。industry 没有下限——它本来就该是"有则报道，没有沉默"。

    第二轮：剩余名额按分数从高到低跨分档补满，直到 total_max，同时仍受
    每分档 _max 上限、max_per_source（同一来源最多几条）、max_per_repo
    （同一仓库最多几条）约束。max_per_repo 是根治 v1 那个 bug 的关键——
    没有它，单一活跃仓库能靠连续发布占满整个 GitHub 板块。

    保底：如果两轮下来仍不满 total_min（比如某天大部分分档都没数据），
    放宽每分档上限继续补，保证"每天至少发这么多条"这条硬约束不被打破。
    但 max_per_source / max_per_repo 这两条多样性上限在保底阶段仍然生效
    ——放宽它们会让保底机制本身变成 v1 那个 bug 的重演（单一来源刷屏）,
    这不是"总量优先"该付出的代价。
    """
    quotas = cfg["quotas"]
    diversity = cfg.get("diversity", {})
    max_per_source = diversity.get("max_per_source")
    max_per_repo = diversity.get("max_per_repo")

    ordered = sorted(items, key=lambda it: it.get("score", 0.0), reverse=True)
    selected: list[dict] = []
    selected_urls: set[str] = set()
    source_counts: dict[str, int] = {}
    repo_counts: dict[str, int] = {}
    cat_counts: dict[str, int] = {c: 0 for c in CATEGORIES}

    def diversity_ok(it: dict) -> bool:
        source = it.get("source", "")
        if max_per_source and source_counts.get(source, 0) >= max_per_source:
            return False
        repo = _extract_repo(it)
        if max_per_repo and repo and repo_counts.get(repo, 0) >= max_per_repo:
            return False
        return True

    def eligible(it: dict) -> bool:
        if it["url"] in selected_urls:
            return False
        if len(selected) >= quotas["total_max"]:
            return False
        cat = it.get("category")
        if cat_counts.get(cat, 0) >= quotas.get(f"{cat}_max", 0):
            return False
        return diversity_ok(it)

    def commit(it: dict) -> None:
        selected.append(it)
        selected_urls.add(it["url"])
        cat = it.get("category")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        source = it.get("source", "")
        source_counts[source] = source_counts.get(source, 0) + 1
        repo = _extract_repo(it)
        if repo:
            repo_counts[repo] = repo_counts.get(repo, 0) + 1

    for cat in ["github", "models", "community", "perspective"]:
        for it in ordered:
            if it.get("category") == cat and eligible(it):
                commit(it)
                break

    for it in ordered:
        if len(selected) >= quotas["total_max"]:
            break
        if it["url"] in selected_urls:
            continue
        if eligible(it):
            commit(it)

    if len(selected) < quotas["total_min"]:
        for it in ordered:
            if len(selected) >= quotas["total_min"]:
                break
            if it["url"] in selected_urls:
                continue
            if diversity_ok(it):
                commit(it)

    return selected
