"""Tests for learning/heuristics.py — H1-H7 heuristics + confidence scoring."""

from __future__ import annotations

import pytest

from stratus.learning.database import LearningDatabase
from stratus.learning.heuristics import (
    _base_score,
    _consistency_factor,
    _recency_factor,
    _scope_factor,
    compute_confidence,
    run_heuristics,
)
from stratus.learning.models import (
    Decision,
    Detection,
    DetectionType,
    PatternCandidate,
    Proposal,
    ProposalType,
)


@pytest.fixture
def db():
    database = LearningDatabase(":memory:")
    yield database
    database.close()


class TestBaseScore:
    def test_code_pattern_minimum(self):
        """Below threshold returns low score."""
        score = _base_score(DetectionType.CODE_PATTERN, 1)
        assert score < 0.3

    def test_code_pattern_at_threshold(self):
        """At threshold of 3 returns moderate score."""
        score = _base_score(DetectionType.CODE_PATTERN, 3)
        assert 0.3 <= score <= 0.7

    def test_code_pattern_high_count(self):
        score = _base_score(DetectionType.CODE_PATTERN, 10)
        assert score > 0.5

    def test_fix_pattern_needs_more(self):
        """Fix patterns need 5+ to score well."""
        score3 = _base_score(DetectionType.FIX_PATTERN, 3)
        score5 = _base_score(DetectionType.FIX_PATTERN, 5)
        assert score5 > score3

    def test_structural_change(self):
        score = _base_score(DetectionType.STRUCTURAL_CHANGE, 2)
        assert score > 0.0

    def test_import_pattern(self):
        score = _base_score(DetectionType.IMPORT_PATTERN, 3)
        assert score > 0.0

    def test_service_detected(self):
        score = _base_score(DetectionType.SERVICE_DETECTED, 1)
        assert score > 0.0


class TestConsistencyFactor:
    def test_empty_instances(self):
        assert _consistency_factor([]) == 1.0

    def test_identical_instances(self):
        instances = [{"pattern": "A"}, {"pattern": "A"}, {"pattern": "A"}]
        factor = _consistency_factor(instances)
        assert factor >= 0.9

    def test_varied_instances(self):
        instances = [{"a": 1}, {"b": 2}, {"c": 3}]
        factor = _consistency_factor(instances)
        assert 0.0 <= factor <= 1.0


class TestRecencyFactor:
    def test_empty_instances(self):
        assert _recency_factor([]) == 1.0

    def test_recent_instances_high_factor(self):
        from datetime import UTC, datetime
        now = datetime.now(UTC).isoformat()
        instances = [{"detected_at": now}]
        factor = _recency_factor(instances)
        assert factor >= 0.8

    def test_no_timestamps(self):
        instances = [{"pattern": "X"}]
        factor = _recency_factor(instances)
        assert factor == 1.0


class TestScopeFactor:
    def test_single_directory(self):
        files = ["src/module/a.py", "src/module/b.py"]
        factor = _scope_factor(files)
        assert factor <= 1.0

    def test_cross_directory(self):
        files = ["src/auth/a.py", "src/billing/b.py", "src/users/c.py"]
        factor = _scope_factor(files)
        assert factor > 1.0

    def test_empty_files(self):
        assert _scope_factor([]) == 1.0


class TestComputeConfidence:
    def test_basic_computation(self):
        d = Detection(
            type=DetectionType.CODE_PATTERN,
            count=5,
            confidence_raw=0.6,
            files=["a.py", "b.py", "c.py"],
            description="test",
            instances=[{"pattern": "X"}],
        )
        confidence = compute_confidence(d)
        assert 0.0 <= confidence <= 1.0

    def test_prior_factor_decreases_confidence(self):
        d = Detection(
            type=DetectionType.CODE_PATTERN,
            count=5,
            confidence_raw=0.6,
            files=["a.py", "b.py"],
            description="test",
        )
        high = compute_confidence(d, prior_factor=1.0)
        low = compute_confidence(d, prior_factor=0.5)
        assert low < high

    def test_capped_at_1(self):
        d = Detection(
            type=DetectionType.CODE_PATTERN,
            count=100,
            confidence_raw=1.0,
            files=["a.py", "b.py", "c.py"],
            description="test",
        )
        confidence = compute_confidence(d, prior_factor=2.0)
        assert confidence <= 1.0


class TestRunHeuristics:
    def test_h1_code_pattern_in_3_files(self, db: LearningDatabase):
        """H1: Same code pattern in 3+ files -> rule proposal."""
        detections = [
            Detection(
                type=DetectionType.CODE_PATTERN,
                count=3,
                confidence_raw=0.6,
                files=["a.py", "b.py", "c.py"],
                description="Repeated error handler",
                instances=[{"file": f} for f in ["a.py", "b.py", "c.py"]],
            ),
        ]
        candidates = run_heuristics(detections, db)
        assert len(candidates) >= 1
        assert candidates[0].detection_type == DetectionType.CODE_PATTERN

    def test_h2_bootstrap_pattern(self, db: LearningDatabase):
        """H2: Same bootstrap pattern for 2+ services -> template."""
        detections = [
            Detection(
                type=DetectionType.STRUCTURAL_CHANGE,
                count=2,
                confidence_raw=0.5,
                files=["services/a/main.py", "services/b/main.py"],
                description="Service bootstrap",
                instances=[{"dir": "a"}, {"dir": "b"}],
            ),
        ]
        candidates = run_heuristics(detections, db)
        assert len(candidates) >= 1

    def test_h3_fix_pattern_in_5_commits(self, db: LearningDatabase):
        """H3: Same fix strategy in 5+ commits -> guideline rule."""
        detections = [
            Detection(
                type=DetectionType.FIX_PATTERN,
                count=5,
                confidence_raw=0.7,
                files=["auth.py", "billing.py", "users.py", "api.py", "core.py"],
                description="Same error fix",
            ),
        ]
        candidates = run_heuristics(detections, db)
        assert len(candidates) >= 1

    def test_h5_new_service_directory(self, db: LearningDatabase):
        """H5: New directory matching service heuristics -> project graph."""
        detections = [
            Detection(
                type=DetectionType.SERVICE_DETECTED,
                count=1,
                confidence_raw=0.5,
                files=["services/payments/main.py"],
                description="New service directory",
            ),
        ]
        candidates = run_heuristics(detections, db)
        assert len(candidates) >= 1

    def test_h7_error_handling_in_4_files(self, db: LearningDatabase):
        """H7: Same error handling in 4+ files -> utility extraction."""
        detections = [
            Detection(
                type=DetectionType.CODE_PATTERN,
                count=4,
                confidence_raw=0.65,
                files=["a.py", "b.py", "c.py", "d.py"],
                description="Repeated error handler: except ValueError",
            ),
        ]
        candidates = run_heuristics(detections, db)
        assert len(candidates) >= 1

    def test_discard_below_count_threshold(self, db: LearningDatabase):
        """Detections with count=1 for code_pattern should be discarded."""
        detections = [
            Detection(
                type=DetectionType.CODE_PATTERN,
                count=1,
                confidence_raw=0.2,
                files=["a.py"],
                description="One-off pattern",
            ),
        ]
        candidates = run_heuristics(detections, db)
        assert len(candidates) == 0

    def test_discard_single_file(self, db: LearningDatabase):
        """All instances in same file should be discarded."""
        detections = [
            Detection(
                type=DetectionType.CODE_PATTERN,
                count=5,
                confidence_raw=0.6,
                files=["a.py"],
                description="Same-file pattern",
            ),
        ]
        candidates = run_heuristics(detections, db)
        # Single-file patterns get discarded
        assert len(candidates) == 0

    def test_cooldown_suppresses_candidate(self, db: LearningDatabase):
        """Recently rejected pattern should be suppressed."""
        # Create and reject a pattern
        c = PatternCandidate(
            id="old-cand",
            detection_type=DetectionType.CODE_PATTERN,
            count=3,
            confidence_raw=0.6,
            confidence_final=0.5,
            files=["a.py", "b.py", "c.py"],
            description="Repeated error handler",
        )
        db.save_candidate(c)
        p = Proposal(
            id="old-prop",
            candidate_id="old-cand",
            type=ProposalType.RULE,
            title="test",
            description="test",
            proposed_content="test",
            confidence=0.5,
        )
        db.save_proposal(p)
        db.decide_proposal("old-prop", Decision.REJECT)

        # Now try to detect same pattern
        detections = [
            Detection(
                type=DetectionType.CODE_PATTERN,
                count=3,
                confidence_raw=0.6,
                files=["a.py", "b.py", "c.py"],
                description="Repeated error handler",
            ),
        ]
        candidates = run_heuristics(detections, db, cooldown_days=7)
        assert len(candidates) == 0

    def test_empty_detections(self, db: LearningDatabase):
        assert run_heuristics([], db) == []
