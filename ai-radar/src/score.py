"""
打分 + 完整性闸门 —— 纯函数，零 LLM，零网络 I/O。

规格来源：PROJECT_SPEC_V2.md §3.4（打分公式）§3.5（完整性闸门）§3.6（关键词表）

设计原则：score_records() 及其子函数只依赖传入的 record 字段和
config/scoring.yaml，不发起任何网络请求、不读写文件（除加载 config 外）。
这样可以在测试里直接用固定输入断言输出，不需要 mock GitHub API ——
见 tests/test_score.py，其中的断言直接使用 §3.5 表格中的四个真实仓库数据。
"""
from __future__ import annotations

import math
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

from src.store import star_growth


def load_config(scoring_path: Path) -> dict:
    with Path(scoring_path).open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _days_since(iso_ts: str | None, as_of: date) -> float:
    """iso_ts 为 None 或无法解析时返回一个很大的天数，等效于"极度陈旧"，
    使 freshness 趋近 0 —— 缺失数据不应被当作"刚刚更新"处理。"""
    if not iso_ts:
        return 9999.0
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return 9999.0
    delta = as_of - dt.astimezone(timezone.utc).date()
    return max(delta.days, 0)


def _min_max_norm(values: list[float]) -> list[float]:
    """对当日全部候选做 min-max 归一化到 [0,1]（§3.4 norm()）。
    全部候选取值相同时（含只有一个候选的情况）返回全 0，避免除零。"""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [0.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def compute_momentum(star_growth_7d: int, stars: int) -> float:
    """归一化增速：除以 sqrt(总星数)，防止大仓库靠基数霸榜（§3.4）。"""
    return star_growth_7d / max(math.sqrt(max(stars, 0)), 1.0)


def compute_adoption(forks: int, contributors: int | None, releases_90d: int | None) -> float:
    """log1p(forks) + log1p(contributors) + log1p(releases_90d)（§3.4）。
    contributors / releases_90d 为 None 表示该仓库未进入 Top 20、未补抓
    （§3.3），按 0 处理 —— 不代表"确认为零"，只是无信息时的保守取值。"""
    c = contributors or 0
    r = releases_90d or 0
    return math.log1p(max(forks, 0)) + math.log1p(c) + math.log1p(r)


def compute_freshness(pushed_at: str | None, as_of: date, half_life_days: float) -> float:
    """距最后提交天数的指数衰减，半衰期 half_life_days（§3.4）。"""
    days = _days_since(pushed_at, as_of)
    return 0.5 ** (days / half_life_days)


def compute_relevance(description: str, topics: list[str], readme_snippet: str, keyword_cfg: dict) -> float:
    """关键词命中数 × 分档权重（§3.6）。大小写不敏感，子串匹配。

    Phase 0 不抓取 README 内容（§3.3 未将其列为采集字段，抓取需要额外
    API 调用），readme_snippet 传空字符串即可 —— relevance 只依赖
    description 与 topics。后续如需接入 README，调用方多传一个字段即可，
    本函数签名不必改动。"""
    haystack = " ".join([description or "", " ".join(topics or []), readme_snippet or ""]).lower()
    score = 0.0
    for tier in keyword_cfg.values():
        weight = tier.get("weight", 0.0)
        for term in tier.get("terms", []):
            if term.lower() in haystack:
                score += weight
    return score


def apply_integrity_gate(record: dict, gate_cfg: dict, as_of: date | None = None) -> dict:
    """硬性否决 / 降权规则（§3.5）。在打分之前执行，独立于 score 公式。

    返回一个新字典（不修改入参），在原 record 基础上追加：
      integrity_action:  "exclude" | "demote_to_template_section"
                          | "flag_for_manual_review" | None
      integrity_reasons: list[str]
      score_multiplier:  float（累乘，默认 1.0）
      fork_star_ratio:   float（供渲染层展示，也便于人工复核阈值是否合理）
    """
    as_of = as_of or date.today()
    stars = record.get("stars", 0)
    forks = record.get("forks", 0)
    contributors = record.get("contributors")
    # Phase 0 已知近似：spec §3.5 的 abandoned 规则写的是"无 release"，
    # 但我们只在 Top 20 候选身上补抓"过去 90 天内的 release 数"（§3.3，
    # 为省 API 额度），并非仓库生命周期内的 release 总数。用 releases_90d==0
    # 作为"无 release"的代理指标——对 90+ 天未提交的仓库而言，这个近似
    # 造成误判的概率很低，但如果未来接入真实 lifetime release 总数，
    # 应替换这里的字段来源。
    releases_90d = record.get("releases_90d")
    days_since_push = _days_since(record.get("pushed_at"), as_of)
    age_days = _days_since(record.get("created_at"), as_of)
    fork_star = forks / max(stars, 1)

    action: str | None = None
    reasons: list[str] = []
    multiplier = 1.0

    inflate_cfg = gate_cfg["suspected_inflation"]
    if stars > inflate_cfg["min_stars"] and fork_star < inflate_cfg["max_fork_star_ratio"]:
        action = inflate_cfg["action"]
        reasons.append(inflate_cfg["reason"])

    template_cfg = gate_cfg["template_not_software"]
    exempt_age = template_cfg.get("exempt_min_age_days")
    is_old_established_project = exempt_age is not None and age_days >= exempt_age
    if action is None and fork_star > template_cfg["min_fork_star_ratio"] and not is_old_established_project:
        action = template_cfg["action"]
        reasons.append(template_cfg["reason"])

    young_cfg = gate_cfg["young_and_huge"]
    if action is None and age_days < young_cfg["max_age_days"] and stars > young_cfg["min_stars"]:
        action = young_cfg["action"]
        reasons.append(young_cfg["reason"])

    single_cfg = gate_cfg["single_maintainer"]
    if (
        stars > single_cfg["min_stars"]
        and contributors is not None
        and contributors <= single_cfg["max_contributors"]
    ):
        multiplier *= single_cfg["score_multiplier"]
        reasons.append(single_cfg["reason"])

    abandoned_cfg = gate_cfg["abandoned"]
    if (
        action is None
        and days_since_push > abandoned_cfg["min_days_since_push"]
        and releases_90d is not None
        and releases_90d <= abandoned_cfg["max_releases_total"]
    ):
        action = "exclude"
        reasons.append(abandoned_cfg["reason"])

    no_license_cfg = gate_cfg["no_license"]
    if not record.get("license"):
        multiplier *= no_license_cfg["score_multiplier"]
        reasons.append(no_license_cfg["reason"])

    return {
        **record,
        "integrity_action": action,
        "integrity_reasons": reasons,
        "score_multiplier": multiplier,
        "fork_star_ratio": round(fork_star, 4),
    }


def score_records(
    records: list[dict],
    history_conn,
    config_path,
    as_of: date | None = None,
) -> list[dict]:
    """对一批当日记录打分。history_conn 是 store.build_memory_db() 返回的
    连接（可以是空连接，见 store.py 文档）——不接受 None，调用方总是先
    build_memory_db()，首次运行没有历史文件时会自然得到一个零行连接，
    此时 star_growth() 对所有仓库返回 0，行为与"没有历史"完全一致。
    """
    cfg = config_path if isinstance(config_path, dict) else load_config(config_path)
    as_of = as_of or date.today()
    weights = cfg["weights"]
    half_life = cfg["freshness_half_life_days"]
    keyword_cfg = cfg["relevance_keywords"]

    gated = [apply_integrity_gate(r, cfg["integrity_gate"], as_of=as_of) for r in records]

    momenta, adoptions, relevances = [], [], []
    for r in gated:
        growth = star_growth(history_conn, r["full_name"], as_of.isoformat(), r.get("stars", 0))
        r["star_growth_7d"] = growth
        r["momentum_raw"] = compute_momentum(growth, r.get("stars", 0))
        r["adoption_raw"] = compute_adoption(r.get("forks", 0), r.get("contributors"), r.get("releases_90d"))
        r["relevance_raw"] = compute_relevance(
            r.get("description", ""), r.get("topics", []), r.get("readme_snippet", ""), keyword_cfg
        )
        r["freshness"] = compute_freshness(r.get("pushed_at"), as_of, half_life)
        momenta.append(r["momentum_raw"])
        adoptions.append(r["adoption_raw"])
        relevances.append(r["relevance_raw"])

    momenta_n = _min_max_norm(momenta)
    adoptions_n = _min_max_norm(adoptions)
    relevances_n = _min_max_norm(relevances)

    for r, m, a, rel in zip(gated, momenta_n, adoptions_n, relevances_n):
        base_score = (
            weights["momentum"] * m
            + weights["adoption"] * a
            + weights["freshness"] * r["freshness"]
            + weights["relevance"] * rel
        )
        r["score"] = base_score * r["score_multiplier"]

    return gated


def partition(scored: list[dict]) -> dict[str, list[dict]]:
    """按 integrity_action 把打分结果分区：
      main     — 主榜（含 flag_for_manual_review 的，附带 ⚠️ 标记）
      template — 移出主榜的模板/配置类仓库
      excluded — 被硬性排除的仓库（疑似刷星 / 已废弃）
      flagged  — main 的子集，仅列出待人工确认的条目，方便渲染层单独提示
    main 与 template 均按 score 降序排列。"""
    main, template, excluded, flagged = [], [], [], []
    for r in scored:
        if r["integrity_action"] == "exclude":
            excluded.append(r)
        elif r["integrity_action"] == "demote_to_template_section":
            template.append(r)
        else:
            main.append(r)
            if r["integrity_action"] == "flag_for_manual_review":
                flagged.append(r)
    main.sort(key=lambda r: r["score"], reverse=True)
    template.sort(key=lambda r: r["score"], reverse=True)
    return {"main": main, "template": template, "excluded": excluded, "flagged": flagged}
