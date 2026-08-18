"""
rank_news.py 的测试 —— 打分公式（新鲜度衰减、实质/噪声关键词）、行业重打标、
配额选取（5 分档 + 多样性上限）。

规格来源：daimonia-trends-radar 改造计划 v2 §四 §六
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.rank_news import quota_select, reclassify_industry, score_all, score_item

CFG = {
    "freshness_half_life_hours": 18,
    "substance_keywords": {"weight": 2.0, "terms": ["开源", "benchmark", "论文"]},
    "noise_keywords": {"weight": -4.0, "terms": ["美联储", "加息", "股价", "楼市"]},
    "alert_keywords": {"weight": 4.0, "terms": ["涨价", "deprecat"]},
    "entity_bonus": {"weight": 1.5, "terms": ["openai", "anthropic"]},
    "industry_keywords": {"terms": ["收购", "融资", "acquisition", "funding", "ipo"]},
    "quotas": {
        "github_max": 4,
        "models_max": 3,
        "community_max": 3,
        "perspective_max": 3,
        "industry_max": 2,
        "total_min": 10,
        "total_max": 12,
    },
    "diversity": {"max_per_source": 3, "max_per_repo": 1},
}

NOW = datetime(2026, 8, 18, 8, 0, tzinfo=timezone.utc)


def make_item(title="标题", url=None, category="community", source="Hacker News", source_weight=1.0, hours_ago=1.0, **overrides):
    item = {
        "title": title,
        "url": url or f"https://example.com/{title}",
        "category": category,
        "source": source,
        "source_weight": source_weight,
        "summary_raw": "",
        "published": (NOW - timedelta(hours=hours_ago)).isoformat(),
        "dup_count": 0,
    }
    item.update(overrides)
    return item


def test_fresher_item_scores_higher_than_older_same_weight():
    fresh = score_item(make_item("A", hours_ago=2), dict(CFG), NOW)
    old = score_item(make_item("B", hours_ago=24), dict(CFG), NOW)
    assert fresh["score"] > old["score"]


def test_missing_published_treated_as_stale_not_excluded():
    """HF trending models/datasets 故意不带 published（见 collect_hf.py），
    缺失时间戳不应该被打成 0 分排除，也不该报错。"""
    item = make_item("C", published=None)
    scored = score_item(item, dict(CFG), NOW)
    assert scored["score"] > 0


def test_substance_keyword_boosts_score():
    with_kw = score_item(make_item("某模型开源，附 benchmark 结果", hours_ago=2), dict(CFG), NOW)
    without_kw = score_item(make_item("某公司发布新产品", hours_ago=2), dict(CFG), NOW)
    assert with_kw["score"] > without_kw["score"]


def test_noise_keyword_penalizes_score():
    """回归测试：v1 翻车的直接原因——泛财经标题必须明显低于技术标题，
    不能再混进要闻区（改造计划 v2 Context）。"""
    noise = score_item(make_item("高盛称市场对美联储加息的预测仍过于激进", hours_ago=1), dict(CFG), NOW)
    technical = score_item(make_item("某推理框架开源，附完整 benchmark", hours_ago=1), dict(CFG), NOW)
    assert noise["score"] < technical["score"]


def test_alert_keyword_is_flagged():
    item = score_item(make_item("某API宣布涨价", hours_ago=1), dict(CFG), NOW)
    assert item["alert"] == "涨价"

    clean = score_item(make_item("某API发布新功能", hours_ago=1), dict(CFG), NOW)
    assert clean["alert"] is None


def test_dup_count_boosts_score():
    """多源报道同一事件（dup_count 更高）应该获得更高分数
    ——这是简报里"N 家媒体报道"标记背后的排序逻辑。"""
    reported_once = score_item(make_item("D", hours_ago=2, dup_count=0), dict(CFG), NOW)
    reported_thrice = score_item(make_item("E", hours_ago=2, dup_count=2), dict(CFG), NOW)
    assert reported_thrice["score"] > reported_once["score"]


def test_reclassify_industry_relabels_matching_items():
    items = [
        make_item("某支付公司据称收购模型路由平台", category="community"),
        make_item("某模型开源，附完整 benchmark", category="perspective"),
    ]
    reclassify_industry(items, CFG["industry_keywords"])
    assert items[0]["category"] == "industry"
    assert items[1]["category"] == "perspective"


def test_reclassify_industry_never_touches_github_category():
    """GitHub release 标题即使偶然命中商业词，也不该被移出 GitHub 板块
    ——它首先是一条技术发布。"""
    items = [make_item("acme/acquisition-toolkit 发布 v3.0.0", category="github")]
    reclassify_industry(items, CFG["industry_keywords"])
    assert items[0]["category"] == "github"


def test_quota_select_fills_each_category_up_to_max():
    """github 候选混用 "GitHub Release" 与 "GitHub Trending" 两个真实存在的
    来源标签（分别对应 collect_gh_events.py 与技能雷达 skill_radar_to_items()），
    避免同一分档内部全部候选共享同一个来源名而被 max_per_source 提前打断
    ——这不是要绕过多样性上限，是让测试反映真实的来源多样性。

    注意：四档 _max 之和是 4+3+3+3=13，超过 total_max=12，所以候选充足时
    不可能四档同时都精确打满——这是配置本身的设计（改造计划 v2 已确认：
    total_max 是硬顶，各档 _max 只是"这一档最多能拿多少"，不是承诺）。
    这里断言每档不超过各自上限、总数打满 total_max，并且优先级最高的
    github（处理顺序里排第一）确实拿到了满额，验证优先级生效。"""
    items = score_all(
        [
            make_item(
                f"gh{i}",
                category="github",
                source="GitHub Release" if i % 2 == 0 else "GitHub Trending",
                url=f"https://github.com/org{i}/repo",
                hours_ago=1,
            )
            for i in range(10)
        ]
        + [make_item(f"models{i}", category="models", source="HF Trending Models", hours_ago=1) for i in range(10)]
        + [make_item(f"community{i}", category="community", hours_ago=1) for i in range(10)]
        + [make_item(f"perspective{i}", category="perspective", source="Simon Willison", hours_ago=1) for i in range(10)],
        dict(CFG),
        NOW,
    )
    selected = quota_select(items, CFG)

    counts = {cat: sum(1 for it in selected if it["category"] == cat) for cat in ["github", "models", "community", "perspective"]}
    for cat, count in counts.items():
        assert count <= CFG["quotas"][f"{cat}_max"]
    assert counts["github"] == CFG["quotas"]["github_max"]  # 最高优先级，候选充足时必须打满
    assert len(selected) == CFG["quotas"]["total_max"]


def test_quota_select_industry_has_no_floor():
    """industry 没有下限——没有商业新闻时，其他分档补满即可，不强行凑数。"""
    items = score_all(
        [make_item(f"gh{i}", category="github", source="GitHub Release", url=f"https://github.com/org{i}/repo", hours_ago=1) for i in range(10)]
        + [make_item(f"models{i}", category="models", source="HF Trending Models", hours_ago=1) for i in range(10)]
        + [make_item(f"community{i}", category="community", hours_ago=1) for i in range(10)]
        + [make_item(f"perspective{i}", category="perspective", source="Simon Willison", hours_ago=1) for i in range(10)],
        dict(CFG),
        NOW,
    )
    selected = quota_select(items, CFG)
    assert sum(1 for it in selected if it["category"] == "industry") == 0


def test_quota_select_respects_industry_max():
    """充足的其他分档候选保证 total_min 不靠"总量优先"保底机制凑数，
    这样才能干净地隔离测试 industry_max 本身有没有生效。"""
    items = score_all(
        [make_item(f"industry{i}", category="industry", hours_ago=1) for i in range(6)]
        + [make_item(f"gh{i}", category="github", source="GitHub Release", url=f"https://github.com/org{i}/repo", hours_ago=1) for i in range(10)]
        + [make_item(f"models{i}", category="models", source="HF Trending Models", hours_ago=1) for i in range(10)]
        + [make_item(f"community{i}", category="community", hours_ago=1) for i in range(10)]
        + [make_item(f"perspective{i}", category="perspective", source="Simon Willison", hours_ago=1) for i in range(10)],
        dict(CFG),
        NOW,
    )
    selected = quota_select(items, CFG)
    assert sum(1 for it in selected if it["category"] == "industry") <= CFG["quotas"]["industry_max"]


def test_quota_select_max_per_repo_caps_same_repo_items():
    """回归测试：v1 那个 bug——同一仓库连续发布不该占满整个 GitHub 板块。
    max_per_repo=1 时，同一仓库的 3 条候选只能入选 1 条。"""
    items = score_all(
        [
            make_item(
                f"acme/hot-repo 发布 v{i}.0.0",
                category="github",
                url=f"https://github.com/acme/hot-repo/releases/tag/v{i}.0.0",
                hours_ago=i,
            )
            for i in range(1, 4)
        ],
        dict(CFG),
        NOW,
    )
    selected = quota_select(items, CFG)
    assert sum(1 for it in selected if it["category"] == "github") == 1


def test_quota_select_max_per_source_caps_same_source_items():
    items = score_all(
        [make_item(f"c{i}", category="community", source="Hacker News", hours_ago=1) for i in range(8)],
        dict(CFG),
        NOW,
    )
    selected = quota_select(items, CFG)
    hn_count = sum(1 for it in selected if it["source"] == "Hacker News")
    assert hn_count <= CFG["diversity"]["max_per_source"]


def test_quota_select_borrows_across_categories_when_one_is_scarce():
    """某个分档当天数据稀薄时，靠其他分档补足到 total_min，而不是少发。
    填充条目每条给一个独立的来源名——这个测试要单独隔离"跨分档补足"这个
    行为，不该和 max_per_source 的限制混在一起（那个有专门的测试覆盖）。"""
    items = score_all(
        [make_item(f"gh{i}", category="github", source="GitHub Release", url=f"https://github.com/org{i}/repo", hours_ago=1) for i in range(2)]
        + [make_item(f"community{i}", category="community", source=f"Source{i}", hours_ago=1) for i in range(15)],
        dict(CFG),
        NOW,
    )
    selected = quota_select(items, CFG)
    assert len(selected) >= CFG["quotas"]["total_min"]


def test_quota_select_never_exceeds_total_max_when_abundant():
    items = score_all(
        [make_item(f"gh{i}", category="github", url=f"https://github.com/org{i}/repo", hours_ago=1) for i in range(20)]
        + [make_item(f"models{i}", category="models", hours_ago=1) for i in range(20)]
        + [make_item(f"community{i}", category="community", hours_ago=1) for i in range(20)]
        + [make_item(f"perspective{i}", category="perspective", hours_ago=1) for i in range(20)],
        dict(CFG),
        NOW,
    )
    selected = quota_select(items, CFG)
    assert len(selected) <= CFG["quotas"]["total_max"]


def test_quota_select_deduplicates_by_url():
    items = score_all(
        [make_item(f"community{i}", category="community", hours_ago=1) for i in range(3)],
        dict(CFG),
        NOW,
    )
    selected = quota_select(items, CFG)
    urls = [it["url"] for it in selected]
    assert len(urls) == len(set(urls))
