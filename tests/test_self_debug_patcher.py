"""Tests for self_debug patcher module."""

from __future__ import annotations

import pytest

from stratus.self_debug.models import (
    GovernanceImpact,
    Issue,
    IssueType,
    PatchProposal,
    RiskLevel,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_issue(
    issue_type: IssueType,
    file_path: str = "src/stratus/foo.py",
    line_start: int = 3,
    line_end: int = 3,
) -> Issue:
    return Issue(
        id=f"{file_path}:{line_start}:{issue_type.value}",
        type=issue_type,
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        description="test description",
        suggestion="test suggestion",
    )


BARE_EXCEPT_SOURCE = """\
def foo():
    try:
        pass
    except:
        pass
"""

UNUSED_IMPORT_SOURCE = """\
import os
import sys

x = sys.argv[0]
"""


# ---------------------------------------------------------------------------
# TestGeneratePatch
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGeneratePatch:
    def test_bare_except_returns_patch_proposal(self):
        from stratus.self_debug.patcher import generate_patch

        issue = _make_issue(IssueType.BARE_EXCEPT, line_start=4, line_end=4)
        result = generate_patch(issue, BARE_EXCEPT_SOURCE)

        assert isinstance(result, PatchProposal)
        assert result.issue_id == issue.id
        assert result.file_path == issue.file_path

    def test_bare_except_diff_replaces_except(self):
        from stratus.self_debug.patcher import generate_patch

        issue = _make_issue(IssueType.BARE_EXCEPT, line_start=4, line_end=4)
        result = generate_patch(issue, BARE_EXCEPT_SOURCE)

        assert result is not None
        assert "except Exception:" in result.unified_diff
        assert "-    except:" in result.unified_diff

    def test_unused_import_returns_patch_proposal(self):
        from stratus.self_debug.patcher import generate_patch

        issue = _make_issue(IssueType.UNUSED_IMPORT, line_start=1, line_end=1)
        result = generate_patch(issue, UNUSED_IMPORT_SOURCE)

        assert isinstance(result, PatchProposal)

    def test_unused_import_diff_removes_line(self):
        from stratus.self_debug.patcher import generate_patch

        issue = _make_issue(IssueType.UNUSED_IMPORT, line_start=1, line_end=1)
        result = generate_patch(issue, UNUSED_IMPORT_SOURCE)

        assert result is not None
        assert "-import os" in result.unified_diff

    def test_missing_type_hint_returns_none(self):
        from stratus.self_debug.patcher import generate_patch

        issue = _make_issue(IssueType.MISSING_TYPE_HINT)
        result = generate_patch(issue, "def foo(): pass\n")

        assert result is None

    def test_dead_code_returns_none(self):
        from stratus.self_debug.patcher import generate_patch

        issue = _make_issue(IssueType.DEAD_CODE)
        result = generate_patch(issue, "x = 1\n")

        assert result is None

    def test_error_handling_returns_none(self):
        from stratus.self_debug.patcher import generate_patch

        issue = _make_issue(IssueType.ERROR_HANDLING)
        result = generate_patch(issue, "x = 1\n")

        assert result is None

    def test_returns_none_when_diff_exceeds_max_lines(self):
        from stratus.self_debug.patcher import generate_patch

        # Build a source with a bare except deep in a large file
        many_lines = "\n".join(f"x{i} = {i}" for i in range(300))
        source = many_lines + "\ntry:\n    pass\nexcept:\n    pass\n"
        issue = _make_issue(IssueType.BARE_EXCEPT, line_start=302, line_end=302)
        result = generate_patch(issue, source, max_lines=5)

        assert result is None

    def test_returns_none_when_governance_impact_is_critical(self):
        from stratus.self_debug.patcher import generate_patch

        # .claude/ path triggers CRITICAL governance impact
        issue = _make_issue(
            IssueType.BARE_EXCEPT,
            file_path=".claude/hooks/something.py",
            line_start=4,
        )
        result = generate_patch(issue, BARE_EXCEPT_SOURCE)

        assert result is None

    def test_unified_diff_starts_with_triple_dashes(self):
        from stratus.self_debug.patcher import generate_patch

        issue = _make_issue(IssueType.BARE_EXCEPT, line_start=4, line_end=4)
        result = generate_patch(issue, BARE_EXCEPT_SOURCE)

        assert result is not None
        assert result.unified_diff.startswith("---")

    def test_unified_diff_contains_plus_plus_plus(self):
        from stratus.self_debug.patcher import generate_patch

        issue = _make_issue(IssueType.BARE_EXCEPT, line_start=4, line_end=4)
        result = generate_patch(issue, BARE_EXCEPT_SOURCE)

        assert result is not None
        assert "+++" in result.unified_diff


# ---------------------------------------------------------------------------
# TestComputeRisk
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestComputeRisk:
    def test_bare_except_is_medium_risk(self):
        from stratus.self_debug.patcher import _compute_risk

        issue = _make_issue(IssueType.BARE_EXCEPT)
        risk = _compute_risk(issue, diff_line_count=5)

        assert risk == RiskLevel.MEDIUM

    def test_unused_import_is_medium_risk(self):
        from stratus.self_debug.patcher import _compute_risk

        issue = _make_issue(IssueType.UNUSED_IMPORT)
        risk = _compute_risk(issue, diff_line_count=3)

        assert risk == RiskLevel.MEDIUM

    def test_large_diff_is_high_risk(self):
        from stratus.self_debug.patcher import _compute_risk

        issue = _make_issue(IssueType.BARE_EXCEPT)
        risk = _compute_risk(issue, diff_line_count=25)

        assert risk == RiskLevel.HIGH


# ---------------------------------------------------------------------------
# TestCheckGovernanceImpact
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCheckGovernanceImpact:
    def test_claude_path_is_critical(self):
        from stratus.self_debug.patcher import _GOVERNANCE_DENYLIST, _check_governance_impact

        impact = _check_governance_impact(".claude/rules/something.md", _GOVERNANCE_DENYLIST)
        assert impact == GovernanceImpact.CRITICAL

    def test_ai_framework_json_is_critical(self):
        from stratus.self_debug.patcher import _GOVERNANCE_DENYLIST, _check_governance_impact

        impact = _check_governance_impact(".ai-framework.json", _GOVERNANCE_DENYLIST)
        assert impact == GovernanceImpact.CRITICAL

    def test_plugin_hooks_is_critical(self):
        from stratus.self_debug.patcher import _GOVERNANCE_DENYLIST, _check_governance_impact

        impact = _check_governance_impact("plugin/hooks/something.py", _GOVERNANCE_DENYLIST)
        assert impact == GovernanceImpact.CRITICAL

    def test_github_path_is_critical(self):
        from stratus.self_debug.patcher import _GOVERNANCE_DENYLIST, _check_governance_impact

        impact = _check_governance_impact(".github/workflows/ci.yml", _GOVERNANCE_DENYLIST)
        assert impact == GovernanceImpact.CRITICAL

    def test_normal_source_file_is_none(self):
        from stratus.self_debug.patcher import _GOVERNANCE_DENYLIST, _check_governance_impact

        impact = _check_governance_impact("src/stratus/foo.py", _GOVERNANCE_DENYLIST)
        assert impact == GovernanceImpact.NONE


# ---------------------------------------------------------------------------
# TestFindAffectedTests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFindAffectedTests:
    def test_finds_test_files_that_reference_module(self, tmp_path):
        from stratus.self_debug.patcher import _find_affected_tests

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_foo.py").write_text("from stratus.foo import bar\n")
        (tests_dir / "test_bar.py").write_text("import something_else\n")

        result = _find_affected_tests("src/stratus/foo.py", tmp_path)

        assert "test_foo.py" in result
        assert "test_bar.py" not in result

    def test_returns_empty_when_no_references(self, tmp_path):
        from stratus.self_debug.patcher import _find_affected_tests

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_bar.py").write_text("import something_else\n")

        result = _find_affected_tests("src/stratus/foo.py", tmp_path)

        assert result == []

    def test_returns_empty_when_no_tests_dir(self, tmp_path):
        from stratus.self_debug.patcher import _find_affected_tests

        result = _find_affected_tests("src/stratus/foo.py", tmp_path)

        assert result == []


# ---------------------------------------------------------------------------
# TestPatchSafety
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPatchSafety:
    def test_unused_import_in_init_returns_none(self):
        from stratus.self_debug.patcher import generate_patch

        issue = _make_issue(
            IssueType.UNUSED_IMPORT,
            file_path="src/stratus/__init__.py",
            line_start=1,
        )
        result = generate_patch(issue, UNUSED_IMPORT_SOURCE)

        assert result is None

    def test_unused_import_in_hooks_path_returns_none(self):
        from stratus.self_debug.patcher import generate_patch

        issue = _make_issue(
            IssueType.UNUSED_IMPORT,
            file_path="src/stratus/hooks/context_monitor.py",
            line_start=1,
        )
        result = generate_patch(issue, UNUSED_IMPORT_SOURCE)

        assert result is None

    def test_unused_import_in_registry_path_returns_none(self):
        from stratus.self_debug.patcher import generate_patch

        issue = _make_issue(
            IssueType.UNUSED_IMPORT,
            file_path="src/stratus/registry/loader.py",
            line_start=1,
        )
        result = generate_patch(issue, UNUSED_IMPORT_SOURCE)

        assert result is None

    def test_unused_import_in_plugin_path_returns_none(self):
        from stratus.self_debug.patcher import generate_patch

        issue = _make_issue(
            IssueType.UNUSED_IMPORT,
            file_path="plugin/commands/init.py",
            line_start=1,
        )
        result = generate_patch(issue, UNUSED_IMPORT_SOURCE)

        assert result is None

    def test_unused_import_in_normal_path_returns_proposal(self):
        from stratus.self_debug.patcher import generate_patch

        issue = _make_issue(
            IssueType.UNUSED_IMPORT,
            file_path="src/stratus/learning/config.py",
            line_start=1,
        )
        result = generate_patch(issue, UNUSED_IMPORT_SOURCE)

        assert isinstance(result, PatchProposal)
