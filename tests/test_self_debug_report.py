"""Tests for self-debug markdown report formatter."""

from __future__ import annotations

import pytest

from stratus.self_debug.models import (
    DebugReport,
    GovernanceImpact,
    Issue,
    IssueType,
    PatchProposal,
    RiskLevel,
)
from stratus.self_debug.report import format_report


def make_issue(
    id: str = "i1",
    type: IssueType = IssueType.BARE_EXCEPT,
    file_path: str = "src/foo.py",
    line_start: int = 10,
    line_end: int = 12,
    description: str = "Bare except clause",
    suggestion: str = "Catch specific exception",
) -> Issue:
    return Issue(
        id=id,
        type=type,
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        description=description,
        suggestion=suggestion,
    )


def make_patch(
    issue_id: str = "i1",
    file_path: str = "src/foo.py",
    unified_diff: str = "-except:\n+except ValueError:\n",
    risk: RiskLevel = RiskLevel.LOW,
    governance_impact: GovernanceImpact = GovernanceImpact.NONE,
    tests_affected: list[str] | None = None,
) -> PatchProposal:
    return PatchProposal(
        issue_id=issue_id,
        file_path=file_path,
        unified_diff=unified_diff,
        risk=risk,
        governance_impact=governance_impact,
        tests_affected=tests_affected or [],
    )


def make_report(
    issues: list[Issue] | None = None,
    patches: list[PatchProposal] | None = None,
    analyzed_files: int = 5,
    skipped_files: int = 1,
    analysis_time_ms: int = 42,
) -> DebugReport:
    return DebugReport(
        issues=issues or [],
        patches=patches or [],
        analyzed_files=analyzed_files,
        skipped_files=skipped_files,
        analysis_time_ms=analysis_time_ms,
    )


@pytest.mark.unit
class TestFormatReport:
    def test_format_report_empty_has_summary_with_zero_counts(self) -> None:

        report = make_report(analyzed_files=3, skipped_files=0, analysis_time_ms=10)
        output = format_report(report)

        assert "# Self-Debug Report" in output
        assert "## Summary" in output
        assert "**Files analyzed:** 3" in output
        assert "**Files skipped:** 0" in output
        assert "**Issues found:** 0" in output
        assert "**Patches generated:** 0" in output
        assert "**Analysis time:** 10ms" in output

    def test_format_report_with_issues_no_patches_shows_issue_descriptions(self) -> None:

        issue = make_issue(description="Bare except clause", suggestion="Use ValueError")
        report = make_report(issues=[issue], patches=[])
        output = format_report(report)

        assert "## Issues" in output
        assert "Bare except clause" in output
        assert "Use ValueError" in output

    def test_format_report_with_issues_and_patches_shows_both(self) -> None:

        issue = make_issue(id="i1")
        patch = make_patch(issue_id="i1", unified_diff="-except:\n+except ValueError:\n")
        report = make_report(issues=[issue], patches=[patch])
        output = format_report(report)

        assert "## Issues" in output
        assert "```diff" in output
        assert "-except:" in output
        assert "+except ValueError:" in output

    def test_format_report_summary_includes_all_counts(self) -> None:

        issues = [make_issue(id="i1"), make_issue(id="i2")]
        patches = [make_patch(issue_id="i1")]
        report = make_report(
            issues=issues,
            patches=patches,
            analyzed_files=10,
            skipped_files=2,
            analysis_time_ms=99,
        )
        output = format_report(report)

        assert "**Files analyzed:** 10" in output
        assert "**Files skipped:** 2" in output
        assert "**Issues found:** 2" in output
        assert "**Patches generated:** 1" in output
        assert "**Analysis time:** 99ms" in output

    def test_format_report_issue_block_shows_file_line_type_description_suggestion(self) -> None:

        issue = make_issue(
            id="i1",
            type=IssueType.UNUSED_IMPORT,
            file_path="src/bar.py",
            line_start=5,
            line_end=5,
            description="Unused import os",
            suggestion="Remove the import",
        )
        report = make_report(issues=[issue], patches=[])
        output = format_report(report)

        assert "src/bar.py" in output
        assert "5" in output
        assert "unused_import" in output
        assert "Unused import os" in output
        assert "Remove the import" in output

    def test_format_report_patch_block_shows_risk_governance_diff(self) -> None:

        issue = make_issue(id="i1")
        patch = make_patch(
            issue_id="i1",
            risk=RiskLevel.HIGH,
            governance_impact=GovernanceImpact.CRITICAL,
            unified_diff="--- a\n+++ b\n-old\n+new\n",
        )
        report = make_report(issues=[issue], patches=[patch])
        output = format_report(report)

        assert "high" in output
        assert "critical" in output
        assert "```diff" in output
        assert "-old" in output
        assert "+new" in output

    def test_format_report_report_only_issues_clearly_marked(self) -> None:

        issue = make_issue(id="i1")
        report = make_report(issues=[issue], patches=[])
        output = format_report(report)

        assert "No patch generated" in output or "report-only" in output.lower()

    def test_format_report_output_is_valid_markdown(self) -> None:

        issue = make_issue(id="i1")
        patch = make_patch(issue_id="i1")
        report = make_report(issues=[issue], patches=[patch])
        output = format_report(report)

        # Valid markdown starts with headings and is a non-empty string
        assert isinstance(output, str)
        assert len(output) > 0
        assert output.startswith("# ")


@pytest.mark.unit
class TestFormatReportEdgeCases:
    def test_format_report_single_issue_no_patch_shows_no_patch_note(self) -> None:

        issue = make_issue(id="i1")
        report = make_report(issues=[issue], patches=[])
        output = format_report(report)

        assert "No patch generated" in output or "report-only" in output.lower()
        assert "## Issues" in output

    def test_format_report_multiple_issues_some_with_patches_some_without(self) -> None:

        issue_with = make_issue(id="i1", description="Has patch")
        issue_without = make_issue(id="i2", description="No patch here")
        patch = make_patch(issue_id="i1", unified_diff="-a\n+b\n")
        report = make_report(issues=[issue_with, issue_without], patches=[patch])
        output = format_report(report)

        assert "Has patch" in output
        assert "No patch here" in output
        assert "```diff" in output
        assert "No patch generated" in output or "report-only" in output.lower()

    def test_format_report_patch_with_empty_tests_affected_no_tests_section(self) -> None:

        issue = make_issue(id="i1")
        patch = make_patch(issue_id="i1", tests_affected=[])
        report = make_report(issues=[issue], patches=[patch])
        output = format_report(report)

        assert "Affected tests" not in output

    def test_format_report_patch_with_tests_affected_shows_list(self) -> None:

        issue = make_issue(id="i1")
        patch = make_patch(
            issue_id="i1",
            tests_affected=["tests/test_foo.py", "tests/test_bar.py"],
        )
        report = make_report(issues=[issue], patches=[patch])
        output = format_report(report)

        assert "Affected tests" in output
        assert "tests/test_foo.py" in output
        assert "tests/test_bar.py" in output
