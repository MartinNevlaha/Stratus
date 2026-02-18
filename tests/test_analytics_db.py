"""Tests for learning/analytics_db.py — analytics CRUD."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from stratus.learning.analytics_db import AnalyticsDB
from stratus.learning.database import LearningDatabase
from stratus.learning.models import (
    FailureCategory,
    FailureEvent,
    RuleBaseline,
)


def _make_db() -> tuple[LearningDatabase, AnalyticsDB]:
    """Create in-memory DB and return both LearningDatabase and AnalyticsDB."""
    db = LearningDatabase(":memory:")
    return db, db.analytics


class TestRecordFailure:
    def test_record_and_count(self):
        db, analytics = _make_db()
        event = FailureEvent(
            category=FailureCategory.LINT_ERROR,
            file_path="src/a.py", detail="ruff: E501",
        )
        result_id = analytics.record_failure(event)
        assert result_id == event.id
        assert analytics.count_failures() == 1
        db.close()

    def test_dedup_same_signature_ignored(self):
        """5x same failure on same day → count stays 1."""
        db, analytics = _make_db()
        for _ in range(5):
            event = FailureEvent(
                category=FailureCategory.LINT_ERROR,
                file_path="src/a.py", detail="ruff: E501",
            )
            analytics.record_failure(event)
        assert analytics.count_failures() == 1
        db.close()

    def test_different_categories_not_deduped(self):
        db, analytics = _make_db()
        e1 = FailureEvent(category=FailureCategory.LINT_ERROR, detail="err")
        e2 = FailureEvent(
            category=FailureCategory.MISSING_TEST, detail="err",
        )
        analytics.record_failure(e1)
        analytics.record_failure(e2)
        assert analytics.count_failures() == 2
        db.close()


class TestCountFailures:
    def test_count_by_category(self):
        db, analytics = _make_db()
        analytics.record_failure(
            FailureEvent(category=FailureCategory.LINT_ERROR, detail="a"),
        )
        analytics.record_failure(
            FailureEvent(category=FailureCategory.MISSING_TEST, detail="b"),
        )
        analytics.record_failure(
            FailureEvent(category=FailureCategory.LINT_ERROR, detail="c"),
        )
        assert analytics.count_failures(
            category=FailureCategory.LINT_ERROR,
        ) == 2
        assert analytics.count_failures(
            category=FailureCategory.MISSING_TEST,
        ) == 1
        db.close()

    def test_count_by_file_path(self):
        db, analytics = _make_db()
        analytics.record_failure(FailureEvent(
            category=FailureCategory.LINT_ERROR,
            file_path="src/a.py", detail="x",
        ))
        analytics.record_failure(FailureEvent(
            category=FailureCategory.LINT_ERROR,
            file_path="src/b.py", detail="y",
        ))
        assert analytics.count_failures(file_path="src/a.py") == 1
        db.close()

    def test_count_with_date_range(self):
        db, analytics = _make_db()
        old_time = (
            datetime.now(UTC) - timedelta(days=60)
        ).isoformat()
        e = FailureEvent(
            category=FailureCategory.LINT_ERROR, detail="old",
            recorded_at=old_time, signature="old-sig",
        )
        analytics.record_failure(e)
        analytics.record_failure(
            FailureEvent(category=FailureCategory.LINT_ERROR, detail="new"),
        )
        since = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        assert analytics.count_failures(since=since) == 1
        db.close()


class TestListFailures:
    def test_list_newest_first(self):
        db, analytics = _make_db()
        e1 = FailureEvent(
            category=FailureCategory.LINT_ERROR, detail="first",
            recorded_at="2026-02-01T00:00:00Z", signature="sig-1",
        )
        e2 = FailureEvent(
            category=FailureCategory.LINT_ERROR, detail="second",
            recorded_at="2026-02-15T00:00:00Z", signature="sig-2",
        )
        analytics.record_failure(e1)
        analytics.record_failure(e2)
        results = analytics.list_failures()
        assert len(results) == 2
        assert results[0].detail == "second"  # newest first
        db.close()

    def test_list_with_limit(self):
        db, analytics = _make_db()
        for i in range(10):
            analytics.record_failure(FailureEvent(
                category=FailureCategory.LINT_ERROR,
                detail=f"err-{i}",
            ))
        results = analytics.list_failures(limit=3)
        assert len(results) == 3
        db.close()


class TestFailureTrends:
    def test_daily_trends(self):
        db, analytics = _make_db()
        analytics.record_failure(FailureEvent(
            category=FailureCategory.LINT_ERROR, detail="day1",
            recorded_at="2026-02-10T10:00:00Z", signature="sig-d1",
        ))
        analytics.record_failure(FailureEvent(
            category=FailureCategory.LINT_ERROR, detail="day2",
            recorded_at="2026-02-11T10:00:00Z", signature="sig-d2",
        ))
        trends = analytics.failure_trends(days=30)
        assert len(trends) >= 2
        counts = {t.period: t.count for t in trends}
        assert counts.get("2026-02-10") == 1
        assert counts.get("2026-02-11") == 1
        db.close()

    def test_trends_filter_by_category(self):
        db, analytics = _make_db()
        analytics.record_failure(FailureEvent(
            category=FailureCategory.LINT_ERROR, detail="lint",
            recorded_at="2026-02-10T10:00:00Z",
        ))
        analytics.record_failure(FailureEvent(
            category=FailureCategory.MISSING_TEST, detail="test",
            recorded_at="2026-02-10T10:00:00Z",
        ))
        trends = analytics.failure_trends(
            category=FailureCategory.LINT_ERROR, days=30,
        )
        assert len(trends) == 1
        assert trends[0].count == 1
        db.close()


class TestFileHotspots:
    def test_hotspots_ranked_by_total(self):
        db, analytics = _make_db()
        for i in range(5):
            analytics.record_failure(FailureEvent(
                category=FailureCategory.LINT_ERROR,
                file_path="src/hot.py", detail=f"err-{i}",
            ))
        for i in range(2):
            analytics.record_failure(FailureEvent(
                category=FailureCategory.LINT_ERROR,
                file_path="src/cold.py", detail=f"err-{i}",
            ))
        hotspots = analytics.file_hotspots(limit=10)
        assert len(hotspots) == 2
        assert hotspots[0].file_path == "src/hot.py"
        assert hotspots[0].total_failures == 5
        db.close()


class TestRuleBaselines:
    def test_save_and_get(self):
        db, analytics = _make_db()
        baseline = RuleBaseline(
            proposal_id="prop-1",
            rule_path=".claude/rules/test.md",
            category=FailureCategory.LINT_ERROR, baseline_count=5,
        )
        analytics.save_baseline(baseline)
        result = analytics.get_baseline(baseline.id)
        assert result is not None
        assert result.proposal_id == "prop-1"
        assert result.baseline_count == 5
        assert result.category_source == "heuristic"
        db.close()

    def test_list_baselines(self):
        db, analytics = _make_db()
        b1 = RuleBaseline(
            proposal_id="p1", rule_path="r1",
            category=FailureCategory.LINT_ERROR, baseline_count=5,
        )
        b2 = RuleBaseline(
            proposal_id="p2", rule_path="r2",
            category=FailureCategory.MISSING_TEST, baseline_count=3,
        )
        analytics.save_baseline(b1)
        analytics.save_baseline(b2)
        baselines = analytics.list_baselines()
        assert len(baselines) == 2
        db.close()

    def test_rebaseline_same_proposal(self):
        """Same proposal_id can have multiple baselines (UUID PK)."""
        db, analytics = _make_db()
        b1 = RuleBaseline(
            proposal_id="prop-1", rule_path="r",
            category=FailureCategory.LINT_ERROR, baseline_count=5,
        )
        b2 = RuleBaseline(
            proposal_id="prop-1", rule_path="r",
            category=FailureCategory.LINT_ERROR, baseline_count=2,
        )
        analytics.save_baseline(b1)
        analytics.save_baseline(b2)
        baselines = analytics.list_baselines()
        assert len(baselines) == 2
        db.close()
