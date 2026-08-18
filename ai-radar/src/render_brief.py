"""
HTML + 纯文本双版本邮件渲染 —— 5 分档（GitHub/模型生态/社区/一线视角/行业动向）。

规格来源：daimonia-trends-radar 改造计划 v2 §一 §四

Gmail 会剥掉 <style> 标签块，所以 HTML 模板全部用内联 CSS（style="..."）。
纯文本版本内容与 HTML 完全一致，供不支持 HTML 的客户端 / 屏幕阅读器使用。

v1 曾经把技能雷达（自建 GitHub star 时间序列）单独放在邮件底部当 3 行
附属区块，v2 把它提升为 GitHub 分档的正文内容之一（run_daily.py 里转成
标准 item 汇入主候选池），这里不再有独立的 skill_radar 参数/区块。
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from jinja2 import Template

CATEGORY_LABELS = {
    "github": "🔧 GitHub：技术是不是真有人做",
    "models": "🤗 模型生态",
    "community": "💬 社区在讨论什么",
    "perspective": "📝 一线视角",
    "industry": "📌 行业动向",
}
CATEGORY_ORDER = ["github", "models", "community", "perspective", "industry"]
_WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def group_by_category(selected: list[dict]) -> dict:
    """把 quota_select() 的扁平列表按 category 分组，组内保持按 score 降序。
    固定 CATEGORY_ORDER 的插入顺序，供模板按此顺序渲染分档。"""
    groups: dict[str, list[dict]] = {c: [] for c in CATEGORY_ORDER}
    for it in sorted(selected, key=lambda x: x.get("score", 0.0), reverse=True):
        groups.setdefault(it.get("category", "community"), []).append(it)
    return groups


def render_subject(selected: list[dict], report_date: date) -> str:
    """头条优先级：GitHub（自建时间序列，最一手的信号）> 模型生态 > 其他。"""
    by_cat = {c: [it for it in selected if it.get("category") == c] for c in CATEGORY_ORDER}
    parts = []
    if by_cat["github"]:
        headline = by_cat["github"][0].get("title_zh") or by_cat["github"][0]["title"]
        parts.append(headline[:16])
    if by_cat["models"]:
        headline = by_cat["models"][0].get("title_zh") or by_cat["models"][0]["title"]
        parts.append(headline[:16])
    highlight = "、".join(parts) if parts else "今日简报"
    return f"AI 简报 · {report_date.isoformat()} · {highlight}"


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """\
<div style="max-width:640px;margin:0 auto;padding:16px;font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;font-size:15px;line-height:1.7;color:#1a1a1a;">
  <h1 style="font-size:20px;margin:0 0 4px;">AI 简报</h1>
  <p style="color:#666;font-size:13px;margin:0 0 20px;">
    {{ report_date }} {{ weekday }} · {{ total }} 条 · 约 90 秒读完
  </p>

  {% for cat, cat_items in categories.items() if cat_items %}
  <h2 style="font-size:16px;border-bottom:1px solid #e5e5e5;padding-bottom:6px;margin:20px 0 12px;">
    {{ labels[cat] }}
  </h2>
  {% for it in cat_items %}
  <div style="margin:0 0 16px;">
    <p style="font-weight:600;margin:0 0 4px;">{{ it.title_zh }}</p>
    {% if it.body_zh %}
    <p style="margin:0 0 4px;color:#333;">{{ it.body_zh }}</p>
    {% endif %}
    <p style="margin:0;font-size:13px;color:#888;">
      <code style="background:#f2f2f2;padding:1px 4px;border-radius:3px;">{{ it.source }}</code>
      · <a href="{{ it.url }}" style="color:#2563eb;text-decoration:none;">原文</a>
      {% if it.dup_count and it.dup_count > 0 %}· {{ it.dup_count + 1 }} 处提及{% endif %}
      {% if it.alert %}· <strong style="color:#c0392b;">⚠️ {{ it.alert }}</strong>{% endif %}
    </p>
  </div>
  {% endfor %}
  {% endfor %}

  <hr style="border:none;border-top:1px solid #e5e5e5;margin:20px 0 8px;">
  <p style="font-size:12px;color:#999;margin:0;">
    候选 {{ stats.raw_total }} → 去重后 {{ stats.deduped_total }} → 入选 {{ stats.selected_total }}
    ｜ 信源 {{ stats.sources_ok }}/{{ stats.sources_total }} 正常{% if stats.failed_sources %}（失败：{{ stats.failed_sources|join('、') }}）{% endif %}
    ｜ LLM: {{ stats.llm_status }}
  </p>
</div>
"""


def render_html(categories: dict, stats: dict, report_date: date) -> str:
    tmpl = Template(HTML_TEMPLATE, trim_blocks=True, lstrip_blocks=True)
    total = sum(len(v) for v in categories.values())
    return tmpl.render(
        categories=categories,
        labels=CATEGORY_LABELS,
        stats=stats,
        report_date=report_date.isoformat(),
        weekday=_WEEKDAY_NAMES[report_date.weekday()],
        total=total,
    )


# ---------------------------------------------------------------------------
# 纯文本
# ---------------------------------------------------------------------------

TEXT_TEMPLATE = """\
AI 简报 · {{ report_date }} {{ weekday }} · {{ total }} 条

{% for cat, cat_items in categories.items() if cat_items %}
━━━ {{ labels[cat] }} ━━━
{% for it in cat_items %}
{{ it.title_zh }}
{% if it.body_zh %}{{ it.body_zh }}
{% endif %}{{ it.source }} · {{ it.url }}{% if it.dup_count and it.dup_count > 0 %} · {{ it.dup_count + 1 }} 处提及{% endif %}{% if it.alert %} · ⚠️ {{ it.alert }}{% endif %}

{% endfor %}
{% endfor %}
━━━ 本次运行 ━━━
候选 {{ stats.raw_total }} → 去重后 {{ stats.deduped_total }} → 入选 {{ stats.selected_total }}
信源 {{ stats.sources_ok }}/{{ stats.sources_total }} 正常{% if stats.failed_sources %}（失败：{{ stats.failed_sources|join('、') }}）{% endif +%}
LLM: {{ stats.llm_status }}
"""


def render_text(categories: dict, stats: dict, report_date: date) -> str:
    tmpl = Template(TEXT_TEMPLATE, trim_blocks=True, lstrip_blocks=True)
    total = sum(len(v) for v in categories.values())
    return tmpl.render(
        categories=categories,
        labels=CATEGORY_LABELS,
        stats=stats,
        report_date=report_date.isoformat(),
        weekday=_WEEKDAY_NAMES[report_date.weekday()],
        total=total,
    )


# ---------------------------------------------------------------------------
# 完整候选榜单（供偶尔人工翻阅，不发邮件）
# ---------------------------------------------------------------------------

FULL_REPORT_TEMPLATE = """\
# AI 简报 —— 完整候选榜单 — {{ report_date }}

_本文件包含当天全部候选（含未入选条目），供偶尔人工翻阅。发进邮箱的是配额选取后的 {{ selected_total }} 条。_

| # | 分类 | 分数 | 标题 | 来源 | 入选 |
|---|---|---|---|---|---|
{% for it in all_items -%}
| {{ loop.index }} | {{ it.category }} | {{ "%.2f"|format(it.score) }} | [{{ it.title }}]({{ it.url }}) | {{ it.source }} | {{ "✅" if it._selected else "" }} |
{% endfor %}
"""


def write_full_report(all_items: list[dict], selected: list[dict], reports_dir: Path, report_date: date) -> Path:
    """写到 {date}-news.md，不是 {date}.md —— 后者是技能雷达管道
    （render.write_report()）的完整榜单文件名，两条管道共用 reports/daily/
    目录，文件名必须分开，否则后写入的会覆盖先写入的。"""
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = reports_dir / f"{report_date.isoformat()}-news.md"
    selected_urls = {it["url"] for it in selected}
    for it in all_items:
        it["_selected"] = it["url"] in selected_urls
    ordered = sorted(all_items, key=lambda it: it.get("score", 0.0), reverse=True)
    tmpl = Template(FULL_REPORT_TEMPLATE, trim_blocks=True, lstrip_blocks=True)
    content = tmpl.render(all_items=ordered, report_date=report_date.isoformat(), selected_total=len(selected))
    out_path.write_text(content, encoding="utf-8")
    return out_path
