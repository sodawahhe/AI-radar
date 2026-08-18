"""
collect_gh_events.is_substantive_release() 的测试 —— release 实质性过滤。

规格来源：daimonia-trends-radar 改造计划 v2 §四 §六

回归测试的原始问题：v1 不加区分地取每仓库最近 5 个 release，导致
"anthropics/claude-code 发布 v2.1.233 / v2.1.232 / v2.1.231" 连续三条
刷屏——这三个都是同一个 minor 版本里的补丁号递增。
"""
from __future__ import annotations

from src.collect_gh_events import is_substantive_release

CFG = {"skip_patch_versions": True, "min_changelog_chars": 80}

LONG_BODY = "What changed: " + "x" * 100  # 超过 min_changelog_chars
SHORT_BODY = "fix typo"  # 远短于 min_changelog_chars


def test_patch_bump_is_not_substantive():
    assert is_substantive_release("v2.1.233", LONG_BODY, CFG) is False
    assert is_substantive_release("v2.1.232", LONG_BODY, CFG) is False


def test_minor_bump_is_substantive():
    assert is_substantive_release("v3.1.0", LONG_BODY, CFG) is True


def test_major_bump_is_substantive():
    assert is_substantive_release("v3.0.0", LONG_BODY, CFG) is True


def test_short_changelog_is_not_substantive_even_with_minor_bump():
    assert is_substantive_release("v3.1.0", SHORT_BODY, CFG) is False


def test_non_semver_tag_not_rejected_by_version_rule():
    """llama.cpp 用 "b10455" 这类构建号，解析不出语义版本时不该被版本规则
    误杀，只受 changelog 长度这一道闸约束。"""
    assert is_substantive_release("b10455", LONG_BODY, CFG) is True
    assert is_substantive_release("b10455", SHORT_BODY, CFG) is False


def test_no_v_prefix_semver_still_parsed():
    """openai-python 这类仓库的 tag 不带 v 前缀（"3.1.0" 而不是 "v3.1.0"）。"""
    assert is_substantive_release("3.1.0", LONG_BODY, CFG) is True
    assert is_substantive_release("3.1.5", LONG_BODY, CFG) is False


def test_skip_patch_versions_disabled_lets_everything_through_version_gate():
    cfg = dict(CFG, skip_patch_versions=False)
    assert is_substantive_release("v2.1.233", LONG_BODY, cfg) is True


def test_empty_body_is_not_substantive():
    assert is_substantive_release("v3.0.0", "", CFG) is False
    assert is_substantive_release("v3.0.0", None, CFG) is False
