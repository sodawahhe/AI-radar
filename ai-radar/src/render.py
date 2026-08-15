"""
Markdown 渲染层 —— 零 LLM 也能跑完整流程（PROJECT_SPEC_V2.md §2.1 强制约束）。

Phase 0 用途：把 score.partition() 的结果渲染成完整排序榜单，供人工判断
"这份榜单是否比 github.com/trending 更有用"（§10 Phase 0 通过标准）。

刻意不套用 §2.4 的邮件硬性配额（MUST_KNOW_MAX 等）—— 那是 Phase 1+
邮件正文的约束。Phase 0 的目的是让你看到*完整*排序结果去评估打分公式
本身是否有效，配额只会挡住这个判断，不该在这里出现。
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from jinja2 import Template

TEMPLATE = """\
# AI Radar — GitHub 技能雷达 — {{ report_date }}

_Phase 0 本地测试运行 · 零 LLM · 未套用邮件配额，展示完整排序结果_
_打分公式：config/scoring.yaml · 规格：PROJECT_SPEC_V2.md §3_

## 运行统计

- 候选总数：{{ stats.total }}
- 通过完整性闸门（主榜）：{{ stats.main_count }}
- 移入模板/配置类：{{ stats.template_count }}
- 被完整性闸门排除：{{ stats.excluded_count }}
- 待人工确认（⚠️，已计入主榜）：{{ stats.flagged_count }}

## 👩‍💻 主榜（按 score 降序）

| # | 仓库 | Score | 7d增速 | Stars | Forks | fork/star | 语言 | 说明 |
|---|---|---|---|---|---|---|---|---|
{% for r in main -%}
| {{ loop.index }} | [{{ r.full_name }}](https://github.com/{{ r.full_name }}){% if r.integrity_action == "flag_for_manual_review" %} ⚠️{% endif %} | {{ "%.3f"|format(r.score) }} | +{{ r.star_growth_7d }} | {{ r.stars }} | {{ r.forks }} | {{ r.fork_star_ratio }} | {{ r.language or "—" }} | {{ (r.description or "")[:80] }} |
{% endfor %}
{% if not main %}
_（无）_
{% endif %}

{% if template %}
## 📋 模板/配置类（fork/star 比例判定为非软件项目，不进主榜）

| 仓库 | Score | Stars | Forks | fork/star | 说明 |
|---|---|---|---|---|---|
{% for r in template -%}
| [{{ r.full_name }}](https://github.com/{{ r.full_name }}) | {{ "%.3f"|format(r.score) }} | {{ r.stars }} | {{ r.forks }} | {{ r.fork_star_ratio }} | {{ (r.description or "")[:80] }} |
{% endfor %}
{% endif %}

{% if excluded %}
## 🚫 被完整性闸门排除

| 仓库 | Stars | Forks | fork/star | 排除理由 |
|---|---|---|---|---|
{% for r in excluded -%}
| {{ r.full_name }} | {{ r.stars }} | {{ r.forks }} | {{ r.fork_star_ratio }} | {{ r.integrity_reasons|join(", ") }} |
{% endfor %}
{% endif %}

---
_由 src/render.py 生成于 {{ report_date }}_
"""


def render_markdown(scored_partitioned: dict, report_date: date | None = None) -> str:
    report_date = report_date or date.today()
    main = scored_partitioned["main"]
    template = scored_partitioned["template"]
    excluded = scored_partitioned["excluded"]
    flagged = scored_partitioned["flagged"]

    stats = {
        "total": len(main) + len(template) + len(excluded),
        "main_count": len(main),
        "template_count": len(template),
        "excluded_count": len(excluded),
        "flagged_count": len(flagged),
    }

    tmpl = Template(TEMPLATE, trim_blocks=True, lstrip_blocks=True)
    return tmpl.render(
        report_date=report_date.isoformat(),
        main=main,
        template=template,
        excluded=excluded,
        stats=stats,
    )


def write_report(scored_partitioned: dict, reports_dir: Path, report_date: date | None = None) -> Path:
    report_date = report_date or date.today()
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = reports_dir / f"{report_date.isoformat()}.md"
    content = render_markdown(scored_partitioned, report_date)
    out_path.write_text(content, encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Phase 1：邮件正文渲染 —— 套用 §2.4 硬性配额 + §6.1/§6.2 的静默日/正常日格式
# ---------------------------------------------------------------------------
#
# 与上面的 render_markdown() 不同：这里*必须*套用配额，因为它的输出会
# 真的发进用户邮箱，而不是给人工检查用的完整调试榜单。
#
# Phase 1 还没有厂商变动监控（§5，Phase 2b）和 LLM 综述（§9.1，Phase 2a），
# 所以这里只有"技能雷达"和"观察"两个区块，也没有"为什么重要"这种需要
# LLM 生成的解读文字 —— 只展示原始事实数据（stars/forks/增速/简介），
# 这正是 §2.1 强制的"零 LLM 也能跑完整流程"。

EMAIL_SILENT_TEMPLATE = """\
今天没有需要你关注的进展。

（候选 {{ stats.total }} 个 · 最高分 {{ "%.3f"|format(top_score) }}，\
未达到关注阈值 {{ "%.2f"|format(silent_threshold) }} · \
完整排序榜单见 reports/daily/{{ report_date }}.md）
"""

EMAIL_NORMAL_TEMPLATE = """\
━━━ 90 秒版 ━━━
{% for r in skill_radar -%}
👩‍💻 [技能] {{ r.full_name }} — score {{ "%.2f"|format(r.score) }} — \
⭐{{ r.stars }}（近7天+{{ r.star_growth_7d }}） — {{ (r.description or "（无简介）")[:40] }}
{% endfor -%}
{% for r in watchlist -%}
👀 [观察] {{ r.full_name }} — score {{ "%.2f"|format(r.score) }} — {{ (r.description or "")[:40] }}
{% endfor %}
━━━ 详情 ━━━
{% for r in skill_radar %}
### {{ r.full_name }}
score {{ "%.3f"|format(r.score) }} | stars {{ r.stars }}（近7天 +{{ r.star_growth_7d }}） | \
forks {{ r.forks }} | fork/star {{ r.fork_star_ratio }} | 语言 {{ r.language or "—" }}
{{ r.description or "（无简介）" }}
https://github.com/{{ r.full_name }}
{% if r.integrity_reasons %}备注：{{ r.integrity_reasons|join(", ") }}{% endif %}
{% endfor %}
━━━ 本次运行 ━━━
候选 {{ stats.total }} → 通过完整性闸门 {{ stats.main_count }} → \
模板区 {{ stats.template_count }} → 排除 {{ stats.excluded_count }}
LLM: 未启用（Phase 1，零 LLM 模式，PROJECT_SPEC_V2.md §2.1）
完整排序榜单见 reports/daily/{{ report_date }}.md
"""


def render_email(
    scored_partitioned: dict,
    quotas: dict,
    silent_threshold: float,
    report_date: date | None = None,
) -> tuple[str, str]:
    """返回 (subject, body)。规格：§2.4（硬性配额）§6.1（静默日）§6.2（正常日）。

    静默日判定：main 分区里的最高分 < silent_threshold。Phase 1 还没有
    厂商变动监控，所以 §6.1 "厂商变动非空时不适用静默日" 这条例外规则
    在这里不生效（等 Phase 2b 接入厂商监控后才需要）。
    """
    report_date = report_date or date.today()
    main = scored_partitioned["main"]
    template = scored_partitioned["template"]
    excluded = scored_partitioned["excluded"]

    stats = {
        "total": len(main) + len(template) + len(excluded),
        "main_count": len(main),
        "template_count": len(template),
        "excluded_count": len(excluded),
    }

    top_score = main[0]["score"] if main else 0.0
    is_silent = top_score < silent_threshold

    if is_silent:
        subject = f"AI Radar — {report_date.isoformat()} — 无需关注"
        tmpl = Template(EMAIL_SILENT_TEMPLATE, trim_blocks=True, lstrip_blocks=True)
        body = tmpl.render(
            stats=stats,
            top_score=top_score,
            silent_threshold=silent_threshold,
            report_date=report_date.isoformat(),
        )
        return subject, body

    skill_radar_max = quotas.get("skill_radar_max", 3)
    watchlist_max = quotas.get("watchlist_max", 3)
    skill_radar = main[:skill_radar_max]
    watchlist = main[skill_radar_max : skill_radar_max + watchlist_max]

    subject = f"AI Radar — {report_date.isoformat()} — {len(skill_radar)} 条技能雷达更新"
    tmpl = Template(EMAIL_NORMAL_TEMPLATE, trim_blocks=True, lstrip_blocks=True)
    body = tmpl.render(
        skill_radar=skill_radar,
        watchlist=watchlist,
        stats=stats,
        report_date=report_date.isoformat(),
    )
    return subject, body
