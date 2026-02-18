"""Tests for orchestration/review.py — verdict parsing and aggregation."""

from __future__ import annotations

from stratus.orchestration.models import (
    FindingSeverity,
    ReviewFinding,
    ReviewVerdict,
    SpecPhase,
    SpecState,
    Verdict,
)
from stratus.orchestration.review import (
    advance_review_iteration,
    aggregate_verdicts,
    build_fix_instructions,
    parse_verdict,
    should_continue_review_loop,
)

# ---------------------------------------------------------------------------
# parse_verdict
# ---------------------------------------------------------------------------


class TestParseVerdict:
    def test_parse_verdict_pass_uppercase_returns_pass(self):
        result = parse_verdict("Verdict: PASS\nLooks good.", "compliance")
        assert result.verdict == Verdict.PASS
        assert result.reviewer == "compliance"

    def test_parse_verdict_fail_uppercase_returns_fail(self):
        result = parse_verdict("Verdict: FAIL\nProblems found.", "quality")
        assert result.verdict == Verdict.FAIL
        assert result.reviewer == "quality"

    def test_parse_verdict_pass_lowercase_case_insensitive(self):
        result = parse_verdict("verdict: pass", "compliance")
        assert result.verdict == Verdict.PASS

    def test_parse_verdict_pass_mixed_case_case_insensitive(self):
        result = parse_verdict("Verdict: Pass\nAll good.", "compliance")
        assert result.verdict == Verdict.PASS

    def test_parse_verdict_fail_mixed_case_case_insensitive(self):
        result = parse_verdict("Verdict: Fail\nIssues found.", "quality")
        assert result.verdict == Verdict.FAIL

    def test_parse_verdict_no_verdict_line_defaults_to_fail(self):
        result = parse_verdict("Some output without a verdict line.", "quality")
        assert result.verdict == Verdict.FAIL

    def test_parse_verdict_empty_input_defaults_to_fail(self):
        result = parse_verdict("", "compliance")
        assert result.verdict == Verdict.FAIL

    def test_parse_verdict_stores_raw_output(self):
        raw = "Verdict: PASS\nAll is well."
        result = parse_verdict(raw, "compliance")
        assert result.raw_output == raw

    def test_parse_verdict_pass_has_no_findings(self):
        result = parse_verdict("Verdict: PASS\nEverything looks good.", "compliance")
        assert result.findings == []

    def test_parse_verdict_must_fix_finding_parsed(self):
        output = "Verdict: FAIL\n- must_fix: Missing input validation"
        result = parse_verdict(output, "quality")
        assert len(result.findings) == 1
        assert result.findings[0].severity == FindingSeverity.MUST_FIX
        assert result.findings[0].description == "Missing input validation"

    def test_parse_verdict_should_fix_finding_parsed(self):
        output = "Verdict: FAIL\n- should_fix: Add type hints to public API"
        result = parse_verdict(output, "quality")
        assert len(result.findings) == 1
        assert result.findings[0].severity == FindingSeverity.SHOULD_FIX
        assert result.findings[0].description == "Add type hints to public API"

    def test_parse_verdict_suggestion_finding_parsed(self):
        output = "Verdict: PASS\n- suggestion: Consider renaming variable"
        result = parse_verdict(output, "quality")
        assert len(result.findings) == 1
        assert result.findings[0].severity == FindingSeverity.SUGGESTION
        assert result.findings[0].description == "Consider renaming variable"

    def test_parse_verdict_finding_with_file_path_and_line(self):
        output = "Verdict: FAIL\n- must_fix: src/app.py:42 — Missing validation"
        result = parse_verdict(output, "compliance")
        assert len(result.findings) == 1
        f = result.findings[0]
        assert f.file_path == "src/app.py"
        assert f.line == 42
        assert "Missing validation" in f.description

    def test_parse_verdict_finding_with_file_path_no_line(self):
        output = "Verdict: FAIL\n- should_fix: src/models.py — Unused import"
        result = parse_verdict(output, "quality")
        assert len(result.findings) == 1
        f = result.findings[0]
        assert f.file_path == "src/models.py"
        assert f.line is None
        assert "Unused import" in f.description

    def test_parse_verdict_finding_without_file_path_uses_empty(self):
        output = "Verdict: FAIL\n- must_fix: Logic error in loop"
        result = parse_verdict(output, "quality")
        assert len(result.findings) == 1
        assert result.findings[0].file_path == ""
        assert result.findings[0].line is None

    def test_parse_verdict_multiple_findings(self):
        output = (
            "Verdict: FAIL\n"
            "- must_fix: src/app.py:10 — SQL injection\n"
            "- should_fix: Missing docstrings\n"
            "- suggestion: Use f-strings"
        )
        result = parse_verdict(output, "quality")
        assert len(result.findings) == 3
        severities = [f.severity for f in result.findings]
        assert FindingSeverity.MUST_FIX in severities
        assert FindingSeverity.SHOULD_FIX in severities
        assert FindingSeverity.SUGGESTION in severities


# ---------------------------------------------------------------------------
# aggregate_verdicts
# ---------------------------------------------------------------------------


class TestAggregateVerdicts:
    def test_aggregate_empty_list_all_passed(self):
        result = aggregate_verdicts([])
        assert result["all_passed"] is True
        assert result["failed_reviewers"] == []
        assert result["total_findings"] == 0
        assert result["must_fix_count"] == 0
        assert result["should_fix_count"] == 0

    def test_aggregate_all_pass_no_findings(self):
        verdicts = [
            ReviewVerdict(reviewer="compliance", verdict=Verdict.PASS, raw_output="Verdict: PASS"),
            ReviewVerdict(reviewer="quality", verdict=Verdict.PASS, raw_output="Verdict: PASS"),
        ]
        result = aggregate_verdicts(verdicts)
        assert result["all_passed"] is True
        assert result["failed_reviewers"] == []
        assert result["total_findings"] == 0

    def test_aggregate_one_fail_reports_reviewer(self):
        verdicts = [
            ReviewVerdict(reviewer="compliance", verdict=Verdict.PASS, raw_output="Verdict: PASS"),
            ReviewVerdict(reviewer="quality", verdict=Verdict.FAIL, raw_output="Verdict: FAIL"),
        ]
        result = aggregate_verdicts(verdicts)
        assert result["all_passed"] is False
        assert "quality" in result["failed_reviewers"]
        assert "compliance" not in result["failed_reviewers"]

    def test_aggregate_multiple_fails_all_reported(self):
        verdicts = [
            ReviewVerdict(reviewer="compliance", verdict=Verdict.FAIL, raw_output="Verdict: FAIL"),
            ReviewVerdict(reviewer="quality", verdict=Verdict.FAIL, raw_output="Verdict: FAIL"),
        ]
        result = aggregate_verdicts(verdicts)
        assert result["all_passed"] is False
        assert set(result["failed_reviewers"]) == {"compliance", "quality"}

    def test_aggregate_counts_findings_by_severity(self):
        finding_must = ReviewFinding(
            file_path="src/a.py", severity=FindingSeverity.MUST_FIX, description="Error"
        )
        finding_should = ReviewFinding(
            file_path="src/b.py", severity=FindingSeverity.SHOULD_FIX, description="Warning"
        )
        finding_suggestion = ReviewFinding(
            file_path="src/c.py", severity=FindingSeverity.SUGGESTION, description="Hint"
        )
        verdicts = [
            ReviewVerdict(
                reviewer="compliance",
                verdict=Verdict.FAIL,
                findings=[finding_must, finding_should],
                raw_output="Verdict: FAIL",
            ),
            ReviewVerdict(
                reviewer="quality",
                verdict=Verdict.FAIL,
                findings=[finding_must, finding_suggestion],
                raw_output="Verdict: FAIL",
            ),
        ]
        result = aggregate_verdicts(verdicts)
        assert result["must_fix_count"] == 2
        assert result["should_fix_count"] == 1
        assert result["total_findings"] == 4


# ---------------------------------------------------------------------------
# build_fix_instructions
# ---------------------------------------------------------------------------


class TestBuildFixInstructions:
    def test_build_fix_instructions_no_findings_returns_empty_string(self):
        verdicts = [
            ReviewVerdict(reviewer="compliance", verdict=Verdict.PASS, raw_output="Verdict: PASS"),
        ]
        result = build_fix_instructions(verdicts)
        assert result == ""

    def test_build_fix_instructions_empty_list_returns_empty_string(self):
        result = build_fix_instructions([])
        assert result == ""

    def test_build_fix_instructions_includes_severity(self):
        finding = ReviewFinding(
            file_path="src/app.py",
            line=10,
            severity=FindingSeverity.MUST_FIX,
            description="Missing validation",
        )
        verdicts = [
            ReviewVerdict(
                reviewer="quality",
                verdict=Verdict.FAIL,
                findings=[finding],
                raw_output="Verdict: FAIL",
            )
        ]
        result = build_fix_instructions(verdicts)
        assert "must_fix" in result
        assert "Missing validation" in result

    def test_build_fix_instructions_groups_by_file_path(self):
        findings = [
            ReviewFinding(
                file_path="src/app.py",
                line=1,
                severity=FindingSeverity.MUST_FIX,
                description="Error A",
            ),
            ReviewFinding(
                file_path="src/app.py",
                line=2,
                severity=FindingSeverity.SHOULD_FIX,
                description="Warning B",
            ),
            ReviewFinding(
                file_path="src/models.py",
                line=5,
                severity=FindingSeverity.SUGGESTION,
                description="Hint C",
            ),
        ]
        verdicts = [
            ReviewVerdict(
                reviewer="quality",
                verdict=Verdict.FAIL,
                findings=findings,
                raw_output="Verdict: FAIL",
            )
        ]
        result = build_fix_instructions(verdicts)
        # src/app.py section should appear once as a heading
        assert result.count("src/app.py") == 1
        assert "src/models.py" in result
        assert "Error A" in result
        assert "Warning B" in result
        assert "Hint C" in result

    def test_build_fix_instructions_includes_line_number(self):
        finding = ReviewFinding(
            file_path="src/app.py",
            line=42,
            severity=FindingSeverity.MUST_FIX,
            description="Critical bug",
        )
        verdicts = [
            ReviewVerdict(
                reviewer="quality",
                verdict=Verdict.FAIL,
                findings=[finding],
                raw_output="Verdict: FAIL",
            )
        ]
        result = build_fix_instructions(verdicts)
        assert "42" in result

    def test_build_fix_instructions_skips_verdicts_with_no_findings(self):
        verdicts = [
            ReviewVerdict(reviewer="compliance", verdict=Verdict.PASS, raw_output="Verdict: PASS"),
            ReviewVerdict(
                reviewer="quality",
                verdict=Verdict.FAIL,
                findings=[
                    ReviewFinding(
                        file_path="src/x.py",
                        severity=FindingSeverity.MUST_FIX,
                        description="Bug",
                    )
                ],
                raw_output="Verdict: FAIL",
            ),
        ]
        result = build_fix_instructions(verdicts)
        assert "src/x.py" in result
        assert "compliance" not in result


# ---------------------------------------------------------------------------
# should_continue_review_loop
# ---------------------------------------------------------------------------


class TestShouldContinueReviewLoop:
    def test_continue_when_iteration_below_max(self):
        state = SpecState(
            phase=SpecPhase.VERIFY, slug="feat", review_iteration=0, max_review_iterations=3
        )
        assert should_continue_review_loop(state) is True

    def test_continue_when_iteration_one_below_max(self):
        state = SpecState(
            phase=SpecPhase.VERIFY, slug="feat", review_iteration=2, max_review_iterations=3
        )
        assert should_continue_review_loop(state) is True

    def test_stop_when_iteration_equals_max(self):
        state = SpecState(
            phase=SpecPhase.VERIFY, slug="feat", review_iteration=3, max_review_iterations=3
        )
        assert should_continue_review_loop(state) is False

    def test_stop_when_iteration_exceeds_max(self):
        state = SpecState(
            phase=SpecPhase.VERIFY, slug="feat", review_iteration=5, max_review_iterations=3
        )
        assert should_continue_review_loop(state) is False


# ---------------------------------------------------------------------------
# advance_review_iteration
# ---------------------------------------------------------------------------


class TestAdvanceReviewIteration:
    def test_advance_increments_review_iteration(self):
        state = SpecState(phase=SpecPhase.VERIFY, slug="feat", review_iteration=0)
        new_state = advance_review_iteration(state)
        assert new_state.review_iteration == 1

    def test_advance_preserves_slug(self):
        state = SpecState(phase=SpecPhase.VERIFY, slug="my-feature", review_iteration=1)
        new_state = advance_review_iteration(state)
        assert new_state.slug == "my-feature"

    def test_advance_preserves_phase(self):
        state = SpecState(phase=SpecPhase.IMPLEMENT, slug="feat", review_iteration=0)
        new_state = advance_review_iteration(state)
        assert new_state.phase == SpecPhase.IMPLEMENT

    def test_advance_preserves_max_review_iterations(self):
        state = SpecState(
            phase=SpecPhase.VERIFY, slug="feat", review_iteration=1, max_review_iterations=5
        )
        new_state = advance_review_iteration(state)
        assert new_state.max_review_iterations == 5

    def test_advance_returns_new_instance(self):
        state = SpecState(phase=SpecPhase.VERIFY, slug="feat", review_iteration=0)
        new_state = advance_review_iteration(state)
        assert new_state is not state
        assert state.review_iteration == 0  # original unchanged

    def test_advance_updates_last_updated(self):
        from datetime import datetime

        state = SpecState(phase=SpecPhase.VERIFY, slug="feat", review_iteration=0)
        new_state = advance_review_iteration(state)
        # last_updated may or may not change depending on timing, but it must be valid ISO
        dt = datetime.fromisoformat(new_state.last_updated)
        assert dt.tzinfo is not None
