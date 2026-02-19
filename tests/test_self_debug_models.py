"""Tests for self_debug/models.py — enums and Pydantic models."""

from __future__ import annotations

from stratus.self_debug.models import (
    DebugReport,
    GovernanceImpact,
    Issue,
    IssueType,
    PatchProposal,
    RiskLevel,
)


class TestIssueType:
    def test_values_are_strings(self):
        assert IssueType.BARE_EXCEPT == "bare_except"
        assert IssueType.UNUSED_IMPORT == "unused_import"
        assert IssueType.MISSING_TYPE_HINT == "missing_type_hint"
        assert IssueType.DEAD_CODE == "dead_code"
        assert IssueType.ERROR_HANDLING == "error_handling"

    def test_is_str(self):
        assert isinstance(IssueType.BARE_EXCEPT, str)

    def test_all_members_present(self):
        members = {m.value for m in IssueType}
        assert members == {
            "bare_except",
            "unused_import",
            "missing_type_hint",
            "dead_code",
            "error_handling",
        }


class TestRiskLevel:
    def test_values_are_strings(self):
        assert RiskLevel.LOW == "low"
        assert RiskLevel.MEDIUM == "medium"
        assert RiskLevel.HIGH == "high"

    def test_is_str(self):
        assert isinstance(RiskLevel.LOW, str)

    def test_all_members_present(self):
        members = {m.value for m in RiskLevel}
        assert members == {"low", "medium", "high"}


class TestGovernanceImpact:
    def test_values_are_strings(self):
        assert GovernanceImpact.NONE == "none"
        assert GovernanceImpact.CRITICAL == "critical"

    def test_is_str(self):
        assert isinstance(GovernanceImpact.NONE, str)

    def test_all_members_present(self):
        members = {m.value for m in GovernanceImpact}
        assert members == {"none", "critical"}


class TestIssue:
    def test_construction_with_valid_data(self):
        issue = Issue(
            id="issue-1",
            type=IssueType.BARE_EXCEPT,
            file_path="src/foo.py",
            line_start=10,
            line_end=12,
            description="Bare except clause found",
            suggestion="Catch specific exception types",
        )
        assert issue.id == "issue-1"
        assert issue.type == IssueType.BARE_EXCEPT
        assert issue.file_path == "src/foo.py"
        assert issue.line_start == 10
        assert issue.line_end == 12
        assert issue.description == "Bare except clause found"
        assert issue.suggestion == "Catch specific exception types"

    def test_all_issue_types_accepted(self):
        for issue_type in IssueType:
            issue = Issue(
                id=f"issue-{issue_type}",
                type=issue_type,
                file_path="a.py",
                line_start=1,
                line_end=1,
                description="desc",
                suggestion="fix it",
            )
            assert issue.type == issue_type

    def test_serializes_to_dict(self):
        issue = Issue(
            id="issue-2",
            type=IssueType.UNUSED_IMPORT,
            file_path="src/bar.py",
            line_start=5,
            line_end=5,
            description="Unused import: os",
            suggestion="Remove the import",
        )
        data = issue.model_dump()
        assert data["id"] == "issue-2"
        assert data["type"] == "unused_import"
        assert data["file_path"] == "src/bar.py"

    def test_round_trip_from_dict(self):
        original = Issue(
            id="issue-3",
            type=IssueType.DEAD_CODE,
            file_path="src/baz.py",
            line_start=20,
            line_end=25,
            description="Unreachable code after return",
            suggestion="Remove the dead code block",
        )
        data = original.model_dump()
        restored = Issue.model_validate(data)
        assert restored == original


class TestPatchProposal:
    def test_construction_with_valid_data(self):
        patch = PatchProposal(
            issue_id="issue-1",
            file_path="src/foo.py",
            unified_diff="--- a/src/foo.py\n+++ b/src/foo.py\n@@ -10,3 +10,3 @@",
            risk=RiskLevel.LOW,
            governance_impact=GovernanceImpact.NONE,
        )
        assert patch.issue_id == "issue-1"
        assert patch.file_path == "src/foo.py"
        assert patch.risk == RiskLevel.LOW
        assert patch.governance_impact == GovernanceImpact.NONE

    def test_tests_affected_defaults_to_empty_list(self):
        patch = PatchProposal(
            issue_id="issue-1",
            file_path="src/foo.py",
            unified_diff="diff content",
            risk=RiskLevel.MEDIUM,
            governance_impact=GovernanceImpact.NONE,
        )
        assert patch.tests_affected == []

    def test_tests_affected_can_be_set(self):
        patch = PatchProposal(
            issue_id="issue-2",
            file_path="src/bar.py",
            unified_diff="diff content",
            risk=RiskLevel.HIGH,
            governance_impact=GovernanceImpact.CRITICAL,
            tests_affected=["tests/test_bar.py", "tests/test_integration.py"],
        )
        assert patch.tests_affected == ["tests/test_bar.py", "tests/test_integration.py"]

    def test_tests_affected_instances_are_independent(self):
        patch1 = PatchProposal(
            issue_id="i1",
            file_path="a.py",
            unified_diff="d",
            risk=RiskLevel.LOW,
            governance_impact=GovernanceImpact.NONE,
        )
        patch2 = PatchProposal(
            issue_id="i2",
            file_path="b.py",
            unified_diff="d",
            risk=RiskLevel.LOW,
            governance_impact=GovernanceImpact.NONE,
        )
        patch1.tests_affected.append("tests/test_a.py")
        assert patch2.tests_affected == []

    def test_serializes_to_dict(self):
        patch = PatchProposal(
            issue_id="issue-3",
            file_path="src/baz.py",
            unified_diff="--- a\n+++ b",
            risk=RiskLevel.MEDIUM,
            governance_impact=GovernanceImpact.NONE,
            tests_affected=["tests/test_baz.py"],
        )
        data = patch.model_dump()
        assert data["issue_id"] == "issue-3"
        assert data["risk"] == "medium"
        assert data["governance_impact"] == "none"
        assert data["tests_affected"] == ["tests/test_baz.py"]

    def test_round_trip_from_dict(self):
        original = PatchProposal(
            issue_id="issue-4",
            file_path="src/qux.py",
            unified_diff="diff",
            risk=RiskLevel.HIGH,
            governance_impact=GovernanceImpact.CRITICAL,
            tests_affected=["tests/test_qux.py"],
        )
        data = original.model_dump()
        restored = PatchProposal.model_validate(data)
        assert restored == original


class TestDebugReport:
    def test_construction_with_valid_data(self):
        report = DebugReport(
            issues=[],
            patches=[],
            analyzed_files=10,
            skipped_files=2,
            analysis_time_ms=350,
        )
        assert report.issues == []
        assert report.patches == []
        assert report.analyzed_files == 10
        assert report.skipped_files == 2
        assert report.analysis_time_ms == 350

    def test_with_issues_and_patches(self):
        issue = Issue(
            id="issue-1",
            type=IssueType.MISSING_TYPE_HINT,
            file_path="src/main.py",
            line_start=3,
            line_end=3,
            description="Function missing return type hint",
            suggestion="Add return type annotation",
        )
        patch = PatchProposal(
            issue_id="issue-1",
            file_path="src/main.py",
            unified_diff="diff content",
            risk=RiskLevel.LOW,
            governance_impact=GovernanceImpact.NONE,
        )
        report = DebugReport(
            issues=[issue],
            patches=[patch],
            analyzed_files=5,
            skipped_files=0,
            analysis_time_ms=120,
        )
        assert len(report.issues) == 1
        assert len(report.patches) == 1
        assert report.issues[0].id == "issue-1"
        assert report.patches[0].issue_id == "issue-1"

    def test_serializes_to_dict(self):
        report = DebugReport(
            issues=[],
            patches=[],
            analyzed_files=3,
            skipped_files=1,
            analysis_time_ms=200,
        )
        data = report.model_dump()
        assert data["analyzed_files"] == 3
        assert data["skipped_files"] == 1
        assert data["analysis_time_ms"] == 200
        assert data["issues"] == []
        assert data["patches"] == []

    def test_round_trip_from_dict(self):
        original = DebugReport(
            issues=[],
            patches=[],
            analyzed_files=7,
            skipped_files=3,
            analysis_time_ms=450,
        )
        data = original.model_dump()
        restored = DebugReport.model_validate(data)
        assert restored == original
