"""Tests for the analytics computation module (Phase 5.1 Step 4)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from stratus.learning.database import LearningDatabase
from stratus.learning.models import (
    FailureCategory,
    FailureEvent,
    FailureTrend,
    RuleBaseline,
    RuleEffectiveness,
)


def _make_failure(
    category: FailureCategory,
    *,
    file_path: str | None = None,
    detail: str = "some error",
    recorded_at: str | None = None,
    signature: str | None = None,
) -> FailureEvent:
    """Helper: build a FailureEvent with optional overrides."""
    event = FailureEvent(category=category, file_path=file_path, detail=detail)
    if recorded_at is not None:
        event = event.model_copy(update={"recorded_at": recorded_at})
    if signature is not None:
        event = event.model_copy(update={"signature": signature})
    return event


@pytest.fixture
def db():
    database = LearningDatabase(":memory:")
    yield database
    database.close()


# ----- 1. empty_db_summary_zeros -----


def test_empty_db_summary_zeros(db):
    from stratus.learning.analytics import compute_failure_summary

    result = compute_failure_summary(db.analytics)

    assert result["total_failures"] == 0
    assert result["daily_rate"] == 0.0
    assert result["period_days"] == 30
    assert result["by_category"] == {}


# ----- 2. summary_with_data -----


def test_summary_with_data(db):
    from stratus.learning.analytics import compute_failure_summary

    analytics = db.analytics
    for i in range(3):
        analytics.record_failure(_make_failure(
            FailureCategory.LINT_ERROR, detail=f"lint {i}", signature=f"sig_lint_{i}"
        ))
    for i in range(2):
        analytics.record_failure(_make_failure(
            FailureCategory.MISSING_TEST, detail=f"test {i}", signature=f"sig_test_{i}"
        ))

    result = compute_failure_summary(analytics, days=30)

    assert result["total_failures"] == 5
    assert result["by_category"][FailureCategory.LINT_ERROR] == 3
    assert result["by_category"][FailureCategory.MISSING_TEST] == 2
    assert result["period_days"] == 30
    assert abs(result["daily_rate"] - 5 / 30) < 1e-9


# ----- 3. trends_delegates -----


def test_trends_delegates(db):
    from stratus.learning.analytics import compute_failure_trends

    analytics = db.analytics
    analytics.record_failure(_make_failure(
        FailureCategory.LINT_ERROR, detail="err", signature="sig_trend_1"
    ))

    trends = compute_failure_trends(analytics, days=30)

    assert isinstance(trends, list)
    assert len(trends) >= 1
    assert all(isinstance(t, FailureTrend) for t in trends)


# ----- 4. hotspots_with_since_cutoff -----


def test_hotspots_with_since_cutoff(db):
    from stratus.learning.analytics import compute_file_hotspots

    analytics = db.analytics
    old_ts = (datetime.now(UTC) - timedelta(days=60)).isoformat()
    recent_ts = (datetime.now(UTC) - timedelta(days=1)).isoformat()

    # Old event — should be excluded by a 30-day since cutoff
    old_event = _make_failure(
        FailureCategory.LINT_ERROR,
        file_path="old_file.py",
        detail="old error",
        signature="sig_old_hotspot",
    )
    old_event = old_event.model_copy(update={"recorded_at": old_ts})
    analytics.record_failure(old_event)

    # Recent event — should be included
    recent_event = _make_failure(
        FailureCategory.LINT_ERROR,
        file_path="recent_file.py",
        detail="recent error",
        signature="sig_recent_hotspot",
    )
    recent_event = recent_event.model_copy(update={"recorded_at": recent_ts})
    analytics.record_failure(recent_event)

    hotspots = compute_file_hotspots(analytics, days=30)

    file_paths = [h.file_path for h in hotspots]
    assert "recent_file.py" in file_paths
    assert "old_file.py" not in file_paths


# ----- 5. systematic_problem_identified -----


def test_systematic_problem_identified(db):
    from stratus.learning.analytics import identify_systematic_problems

    analytics = db.analytics
    # Seed 40 lint errors — daily_rate = 40/30 ≈ 1.33 → systematic_problem
    for i in range(40):
        analytics.record_failure(_make_failure(
            FailureCategory.LINT_ERROR, detail=f"err {i}", signature=f"sig_sys_{i}"
        ))

    problems = identify_systematic_problems(analytics, days=30, min_count=5)

    assert len(problems) == 1
    assert problems[0]["category"] == FailureCategory.LINT_ERROR
    assert problems[0]["count"] == 40
    assert problems[0]["assessment"] == "systematic_problem"


# ----- 6. occasional_not_returned -----


def test_occasional_not_returned(db):
    from stratus.learning.analytics import identify_systematic_problems

    analytics = db.analytics
    # Only 2 failures — below min_count=5
    for i in range(2):
        analytics.record_failure(_make_failure(
            FailureCategory.REVIEW_FAILURE, detail=f"rev {i}", signature=f"sig_occ_{i}"
        ))

    problems = identify_systematic_problems(analytics, days=30, min_count=5)

    assert problems == []


# ----- 7. baseline_creation_counts_failures -----


def test_baseline_creation_counts_failures(db):
    from stratus.learning.analytics import snapshot_baseline

    analytics = db.analytics
    for i in range(7):
        analytics.record_failure(_make_failure(
            FailureCategory.MISSING_TEST, detail=f"missing {i}", signature=f"sig_base_{i}"
        ))
    # Different category — should NOT be counted
    analytics.record_failure(_make_failure(
        FailureCategory.LINT_ERROR, detail="lint x", signature="sig_base_lint"
    ))

    baseline = snapshot_baseline(
        analytics,
        proposal_id="prop-001",
        rule_path="rules/my_rule.md",
        category=FailureCategory.MISSING_TEST,
    )

    assert isinstance(baseline, RuleBaseline)
    assert baseline.proposal_id == "prop-001"
    assert baseline.rule_path == "rules/my_rule.md"
    assert baseline.category == FailureCategory.MISSING_TEST
    assert baseline.baseline_count == 7
    assert baseline.baseline_window_days == 30

    # Verify it was persisted
    saved = analytics.get_baseline(baseline.id)
    assert saved is not None
    assert saved.baseline_count == 7


# ----- 8. effective_rule_scoring -----


def test_effective_rule_scoring(db):
    from stratus.learning.analytics import compute_rule_effectiveness

    analytics = db.analytics
    # Baseline: 60 failures over 30 days → baseline_rate = 2.0/day
    past_ts = (datetime.now(UTC) - timedelta(days=5)).isoformat()
    baseline = RuleBaseline(
        proposal_id="prop-eff",
        rule_path="rules/eff.md",
        category=FailureCategory.LINT_ERROR,
        baseline_count=60,
        baseline_window_days=30,
        created_at=past_ts,
    )
    analytics.save_baseline(baseline)

    # After baseline: only 2 failures in last 5 days → current_rate ≈ 0.4/day
    for i in range(2):
        analytics.record_failure(_make_failure(
            FailureCategory.LINT_ERROR, detail=f"new {i}", signature=f"sig_eff_{i}"
        ))

    result = compute_rule_effectiveness(analytics, baseline)

    assert isinstance(result, RuleEffectiveness)
    assert result.verdict == "effective"
    assert result.effectiveness_score > 0.6


# ----- 9. neutral_rule_scoring -----


def test_neutral_rule_scoring(db):
    from stratus.learning.analytics import compute_rule_effectiveness

    analytics = db.analytics
    # Baseline: 5 failures over 10 days → baseline_rate = 0.5/day
    past_ts = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    baseline = RuleBaseline(
        proposal_id="prop-neut",
        rule_path="rules/neut.md",
        category=FailureCategory.MISSING_TEST,
        baseline_count=5,
        baseline_window_days=10,
        created_at=past_ts,
    )
    analytics.save_baseline(baseline)

    # After baseline: 5 failures over 10 days → current_rate = 0.5/day (same)
    # ratio = 0.5 / 0.5 = 1.0 → score = clamp(1.0 - 1.0/2.0) = 0.5 → neutral
    for i in range(5):
        analytics.record_failure(_make_failure(
            FailureCategory.MISSING_TEST, detail=f"nt {i}", signature=f"sig_neut_{i}"
        ))

    result = compute_rule_effectiveness(analytics, baseline)

    assert result.verdict == "neutral"
    assert 0.4 <= result.effectiveness_score <= 0.6


# ----- 10. ineffective_rule_scoring -----


def test_ineffective_rule_scoring(db):
    from stratus.learning.analytics import compute_rule_effectiveness

    analytics = db.analytics
    # Baseline: 2 failures over 10 days → baseline_rate = 0.2/day
    past_ts = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    baseline = RuleBaseline(
        proposal_id="prop-ineff",
        rule_path="rules/ineff.md",
        category=FailureCategory.CONTEXT_OVERFLOW,
        baseline_count=2,
        baseline_window_days=10,
        created_at=past_ts,
    )
    analytics.save_baseline(baseline)

    # After baseline: 30 failures over 10 days → current_rate = 3.0/day
    # ratio = 3.0 / 0.2 = 15.0 → score = clamp(1.0 - 15.0/2.0) = clamp(-6.5) = 0.0
    for i in range(30):
        analytics.record_failure(_make_failure(
            FailureCategory.CONTEXT_OVERFLOW, detail=f"co {i}", signature=f"sig_ineff_{i}"
        ))

    result = compute_rule_effectiveness(analytics, baseline)

    assert result.verdict == "ineffective"
    assert result.effectiveness_score < 0.4


# ----- 11. baseline_rate_zero_edge_case -----


def test_baseline_rate_zero_edge_case(db):
    from stratus.learning.analytics import compute_rule_effectiveness

    analytics = db.analytics
    # Baseline: 0 failures → baseline_rate effectively 0, eps kicks in
    past_ts = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    baseline = RuleBaseline(
        proposal_id="prop-zero",
        rule_path="rules/zero.md",
        category=FailureCategory.REVIEW_FAILURE,
        baseline_count=0,
        baseline_window_days=10,
        created_at=past_ts,
    )
    analytics.save_baseline(baseline)

    # Current: 0 failures → current_rate = 0 → ratio = 0/eps
    result = compute_rule_effectiveness(analytics, baseline)

    # Should not raise; with current_rate=0 and baseline_rate effectively eps=0.01:
    # ratio = 0 / 0.01 = 0.0 → score = clamp(1.0 - 0/2.0) = 1.0 → effective
    assert result is not None
    assert result.effectiveness_score >= 0.0
    assert result.effectiveness_score <= 1.0
