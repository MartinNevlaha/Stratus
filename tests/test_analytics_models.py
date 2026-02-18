"""Tests for analytics Pydantic models in learning/models.py."""

from __future__ import annotations

from stratus.learning.models import (
    FailureCategory,
    FailureEvent,
    FailureTrend,
    FileHotspot,
    RuleBaseline,
    RuleEffectiveness,
)


class TestFailureCategory:
    def test_enum_values(self):
        assert FailureCategory.LINT_ERROR == "lint_error"
        assert FailureCategory.MISSING_TEST == "missing_test"
        assert FailureCategory.CONTEXT_OVERFLOW == "context_overflow"
        assert FailureCategory.REVIEW_FAILURE == "review_failure"


class TestFailureEvent:
    def test_create_with_defaults(self):
        e = FailureEvent(category=FailureCategory.LINT_ERROR)
        assert e.id != ""
        assert e.recorded_at != ""
        assert e.file_path is None
        assert e.detail == ""
        assert e.session_id is None
        assert e.signature != ""

    def test_create_with_all_fields(self):
        e = FailureEvent(
            category=FailureCategory.MISSING_TEST,
            file_path="src/auth.py",
            detail="No test file",
            session_id="sess-1",
        )
        assert e.category == FailureCategory.MISSING_TEST
        assert e.file_path == "src/auth.py"
        assert e.detail == "No test file"

    def test_signature_deterministic(self):
        e1 = FailureEvent(
            category=FailureCategory.LINT_ERROR,
            file_path="src/a.py",
            detail="ruff: error",
        )
        e2 = FailureEvent(
            category=FailureCategory.LINT_ERROR,
            file_path="src/a.py",
            detail="ruff: error",
        )
        assert e1.signature == e2.signature

    def test_signature_differs_for_different_content(self):
        e1 = FailureEvent(
            category=FailureCategory.LINT_ERROR,
            file_path="src/a.py",
            detail="ruff: error",
        )
        e2 = FailureEvent(
            category=FailureCategory.MISSING_TEST,
            file_path="src/a.py",
            detail="ruff: error",
        )
        assert e1.signature != e2.signature


class TestRuleBaseline:
    def test_create_with_defaults(self):
        b = RuleBaseline(
            proposal_id="prop-1",
            rule_path=".claude/rules/test.md",
            category=FailureCategory.LINT_ERROR,
            baseline_count=5,
        )
        assert b.id != ""
        assert b.baseline_window_days == 30
        assert b.created_at != ""
        assert b.category_source == "heuristic"

    def test_create_with_override_source(self):
        b = RuleBaseline(
            proposal_id="prop-1",
            rule_path=".claude/rules/test.md",
            category=FailureCategory.REVIEW_FAILURE,
            baseline_count=3,
            category_source="manual",
        )
        assert b.category_source == "manual"


class TestRuleEffectiveness:
    def test_create(self):
        r = RuleEffectiveness(
            proposal_id="prop-1",
            rule_path=".claude/rules/test.md",
            category=FailureCategory.LINT_ERROR,
            baseline_rate=2.0,
            current_rate=1.0,
            effectiveness_score=0.75,
            sample_days=30,
            verdict="effective",
        )
        assert r.verdict == "effective"
        assert r.effectiveness_score == 0.75


class TestFailureTrend:
    def test_create(self):
        t = FailureTrend(
            category=FailureCategory.LINT_ERROR,
            period="2026-02-10",
            count=5,
        )
        assert t.count == 5


class TestFileHotspot:
    def test_create(self):
        h = FileHotspot(
            file_path="src/auth.py",
            total_failures=10,
            by_category={"lint_error": 7, "missing_test": 3},
        )
        assert h.total_failures == 10
        assert h.by_category["lint_error"] == 7
