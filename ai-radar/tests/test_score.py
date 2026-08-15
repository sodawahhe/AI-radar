"""
score.py 的完整性闸门测试 —— 直接用 PROJECT_SPEC_V2.md §3.5 的实测数据做断言。

这四个仓库不是虚构的测试夹具：odysseus-dev/odysseus、ultraworkers/claw-code、
JuliusBrussee/caveman、cloudflare/computer 是 2026-08-15 通过 GitHub Search API
实测抓取到的真实仓库，star/fork 数字直接取自方案调研阶段的实测结果
（见 PROJECT_SPEC_V2.md §3.5 表格）。这样一来，谁要是把完整性闸门的阈值改坏，
测试立刻会红，而不是等到某天邮件里混进一个刷星仓库才发现。
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

from src.score import apply_integrity_gate, load_config, partition, score_records
from src.store import SNAPSHOT_SCHEMA


@pytest.fixture
def scoring_config():
    cfg_path = Path(__file__).resolve().parent.parent / "config" / "scoring.yaml"
    return load_config(cfg_path)


@pytest.fixture
def empty_history_conn():
    conn = sqlite3.connect(":memory:")
    conn.execute(SNAPSHOT_SCHEMA)
    conn.commit()
    return conn


def _iso_days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat() + "T00:00:00Z"


def make_record(full_name, stars, forks, **overrides):
    record = {
        "full_name": full_name,
        "stars": stars,
        "forks": forks,
        "open_issues": 10,
        "watchers": stars,
        "pushed_at": _iso_days_ago(3),
        "created_at": _iso_days_ago(200),
        "license": "MIT",
        "language": "Python",
        "topics": [],
        "description": "",
        "contributors": 20,
        "releases_90d": 2,
    }
    record.update(overrides)
    return record


# --- §3.5 实测数据：直接断言四个真实仓库的完整性闸门判定 ---


def test_odysseus_excluded_as_suspected_inflation(scoring_config):
    """odysseus-dev/odysseus: 85,390 stars / 458 forks -> fork_star=0.00536 < 0.01
    且 stars > 5000 -> 必须被排除（suspected_star_inflation）。"""
    record = make_record("odysseus-dev/odysseus", stars=85390, forks=458)
    result = apply_integrity_gate(record, scoring_config["integrity_gate"])
    assert result["integrity_action"] == "exclude"
    assert "suspected_star_inflation" in result["integrity_reasons"]


def test_claw_code_demoted_as_template(scoring_config):
    """ultraworkers/claw-code: 195,047 stars / 109,123 forks -> fork_star=0.56 > 0.40
    -> 必须移出主榜，判定为模板/配置类而非软件（template_not_software）。"""
    record = make_record("ultraworkers/claw-code", stars=195047, forks=109123)
    result = apply_integrity_gate(record, scoring_config["integrity_gate"])
    assert result["integrity_action"] == "demote_to_template_section"
    assert "template_not_software" in result["integrity_reasons"]


def test_caveman_passes_gate_despite_low_value(scoring_config):
    """JuliusBrussee/caveman: 98,269 stars / 5,680 forks -> fork_star=0.058，
    落在健康区间 0.05-0.15 内，不应被闸门排除或降级 —— 这正是 §3.5
    说明的"闸门边界"：比例正常但仍是低价值的注意力产品，只能靠
    relevance 权重压低排名，不能靠完整性规则否决。"""
    record = make_record("JuliusBrussee/caveman", stars=98269, forks=5680)
    result = apply_integrity_gate(record, scoring_config["integrity_gate"])
    assert result["integrity_action"] is None


def test_old_established_project_exempt_from_template_gate(scoring_config):
    """2026-08-15 真实数据测试发现：pandas-dev/pandas（存在 17 年）
    stars=49501 forks=20267 -> fork_star=0.409 > 0.40，曾被误判为模板仓库。
    修复后：存在超过 5 年（exempt_min_age_days）的老项目不适用这条规则。"""
    record = make_record(
        "pandas-dev/pandas",
        stars=49501,
        forks=20267,
        created_at=_iso_days_ago(17 * 365),
    )
    result = apply_integrity_gate(record, scoring_config["integrity_gate"])
    assert result["integrity_action"] is None


def test_young_repo_still_demoted_despite_high_fork_ratio(scoring_config):
    """反面验证：同样的高 fork/star 比例，若仓库很年轻（不满 5 年），
    仍然要被判定为模板仓库 —— 年龄豁免不能变成"什么都不查了"。"""
    record = make_record(
        "someorg/definitely-a-template",
        stars=50000,
        forks=25000,  # fork_star = 0.50，同样超过阈值
        created_at=_iso_days_ago(100),  # 远小于 5 年
    )
    result = apply_integrity_gate(record, scoring_config["integrity_gate"])
    assert result["integrity_action"] == "demote_to_template_section"


def test_cloudflare_computer_passes_gate(scoring_config):
    """cloudflare/computer: 8,160 stars，健康新项目 -> 必须通过完整性闸门。"""
    record = make_record(
        "cloudflare/computer",
        stars=8160,
        forks=380,
        description="Give your agent a computer",
        topics=["ai-agents", "sandbox"],
    )
    result = apply_integrity_gate(record, scoring_config["integrity_gate"])
    assert result["integrity_action"] is None


# --- 完整性闸门的其余规则单独测试 ---


def test_young_and_huge_flagged_not_excluded(scoring_config):
    """新仓库（<30天）却已有 2 万+ star -> 标记待人工确认，但不排除。"""
    record = make_record(
        "someorg/overnight-sensation",
        stars=25000,
        forks=1200,  # fork_star ≈ 0.048，正常范围，不触发其他闸门
        created_at=_iso_days_ago(10),
    )
    result = apply_integrity_gate(record, scoring_config["integrity_gate"])
    assert result["integrity_action"] == "flag_for_manual_review"


def test_single_maintainer_downweighted_not_excluded(scoring_config):
    """1万+ star 但只有 1-2 个贡献者 -> score 打 5 折，但不排除、不降级分区。"""
    record = make_record("soloauthor/big-project", stars=15000, forks=900, contributors=1)
    result = apply_integrity_gate(record, scoring_config["integrity_gate"])
    assert result["integrity_action"] is None
    assert result["score_multiplier"] == pytest.approx(0.5)


def test_abandoned_repo_excluded(scoring_config):
    """90+ 天无提交且（近 90 天内）无 release -> 排除。"""
    record = make_record(
        "oldproject/dead",
        stars=3000,
        forks=200,
        pushed_at=_iso_days_ago(180),
        releases_90d=0,
    )
    result = apply_integrity_gate(record, scoring_config["integrity_gate"])
    assert result["integrity_action"] == "exclude"
    assert "abandoned" in result["integrity_reasons"]


def test_no_license_downweighted(scoring_config):
    record = make_record("noone/no-license-repo", stars=2000, forks=150, license=None)
    result = apply_integrity_gate(record, scoring_config["integrity_gate"])
    assert result["score_multiplier"] == pytest.approx(0.7)


def test_healthy_repo_untouched(scoring_config):
    """健康仓库（有 license、多贡献者、比例正常）不应触发任何降权。"""
    record = make_record("healthy/project", stars=5000, forks=400, contributors=30)
    result = apply_integrity_gate(record, scoring_config["integrity_gate"])
    assert result["integrity_action"] is None
    assert result["score_multiplier"] == pytest.approx(1.0)


# --- score_records() 端到端 + partition() 分区验证 ---


def test_score_records_end_to_end_partitions_correctly(scoring_config, empty_history_conn):
    records = [
        make_record("odysseus-dev/odysseus", stars=85390, forks=458),
        make_record("ultraworkers/claw-code", stars=195047, forks=109123),
        make_record(
            "cloudflare/computer",
            stars=8160,
            forks=380,
            description="Give your agent a computer, agent sandbox",
            topics=["ai-agents"],
        ),
    ]
    scored = score_records(records, empty_history_conn, scoring_config, as_of=date.today())
    result = partition(scored)

    main_names = {r["full_name"] for r in result["main"]}
    template_names = {r["full_name"] for r in result["template"]}
    excluded_names = {r["full_name"] for r in result["excluded"]}

    assert "cloudflare/computer" in main_names
    assert "ultraworkers/claw-code" in template_names
    assert "odysseus-dev/odysseus" in excluded_names

    # 主榜必须按 score 降序排列
    scores = [r["score"] for r in result["main"]]
    assert scores == sorted(scores, reverse=True)


def test_score_records_first_run_momentum_is_zero(scoring_config, empty_history_conn):
    """首次运行（无历史快照）时，所有仓库的 momentum 必须为 0 ——
    排序完全由 adoption/freshness/relevance 决定，这是 store.py 文档中
    明确的预期行为，不是 bug（PROJECT_SPEC_V2.md §3.3 / store.py 注释）。"""
    records = [make_record("a/b", stars=1000, forks=100)]
    scored = score_records(records, empty_history_conn, scoring_config, as_of=date.today())
    assert scored[0]["star_growth_7d"] == 0
    assert scored[0]["momentum_raw"] == 0.0
