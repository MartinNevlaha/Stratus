"""Tests for learning/database.py — CRUD operations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from stratus.learning.database import LearningDatabase
from stratus.learning.models import (
    CandidateStatus,
    Decision,
    DetectionType,
    LLMAssessment,
    PatternCandidate,
    Proposal,
    ProposalStatus,
    ProposalType,
)


@pytest.fixture
def db():
    database = LearningDatabase(":memory:")
    yield database
    database.close()


def _make_candidate(**overrides) -> PatternCandidate:
    defaults = dict(
        id="cand-1",
        detection_type=DetectionType.CODE_PATTERN,
        count=3,
        confidence_raw=0.6,
        confidence_final=0.5,
        files=["a.py", "b.py"],
        description="Repeated error handling pattern",
        instances=[{"file": "a.py", "line": 10}],
    )
    defaults.update(overrides)
    return PatternCandidate(**defaults)


def _make_proposal(**overrides) -> Proposal:
    defaults = dict(
        id="prop-1",
        candidate_id="cand-1",
        type=ProposalType.RULE,
        title="Error handling rule",
        description="Use consistent error handlers",
        proposed_content="Always wrap external calls...",
        confidence=0.7,
    )
    defaults.update(overrides)
    return Proposal(**defaults)


class TestSaveCandidate:
    def test_save_and_get(self, db: LearningDatabase):
        c = _make_candidate()
        db.save_candidate(c)
        result = db.get_candidate("cand-1")
        assert result is not None
        assert result.id == "cand-1"
        assert result.detection_type == DetectionType.CODE_PATTERN
        assert result.count == 3
        assert result.files == ["a.py", "b.py"]

    def test_save_preserves_all_fields(self, db: LearningDatabase):
        c = _make_candidate(
            status=CandidateStatus.INTERPRETED,
            description_hash="custom-hash",
        )
        db.save_candidate(c)
        result = db.get_candidate("cand-1")
        assert result is not None
        assert result.status == CandidateStatus.INTERPRETED
        assert result.description_hash == "custom-hash"
        assert result.confidence_raw == 0.6
        assert result.confidence_final == 0.5

    def test_get_nonexistent_returns_none(self, db: LearningDatabase):
        assert db.get_candidate("nope") is None


class TestListCandidates:
    def test_list_by_status(self, db: LearningDatabase):
        db.save_candidate(_make_candidate(id="c1", status=CandidateStatus.PENDING))
        db.save_candidate(_make_candidate(id="c2", status=CandidateStatus.PROPOSED))
        db.save_candidate(_make_candidate(id="c3", status=CandidateStatus.PENDING))

        pending = db.list_candidates(status=CandidateStatus.PENDING)
        assert len(pending) == 2

    def test_list_by_min_confidence(self, db: LearningDatabase):
        db.save_candidate(_make_candidate(id="c1", confidence_final=0.3))
        db.save_candidate(_make_candidate(id="c2", confidence_final=0.8))
        db.save_candidate(_make_candidate(id="c3", confidence_final=0.6))

        results = db.list_candidates(min_confidence=0.5)
        assert len(results) == 2
        ids = {r.id for r in results}
        assert ids == {"c2", "c3"}

    def test_list_with_limit(self, db: LearningDatabase):
        for i in range(10):
            db.save_candidate(_make_candidate(id=f"c{i}"))
        results = db.list_candidates(limit=3)
        assert len(results) == 3

    def test_list_empty(self, db: LearningDatabase):
        assert db.list_candidates() == []


class TestUpdateCandidateStatus:
    def test_update_status(self, db: LearningDatabase):
        db.save_candidate(_make_candidate())
        db.update_candidate_status("cand-1", CandidateStatus.PROPOSED)
        result = db.get_candidate("cand-1")
        assert result is not None
        assert result.status == CandidateStatus.PROPOSED

    def test_update_with_llm_assessment(self, db: LearningDatabase):
        db.save_candidate(_make_candidate())
        assessment = LLMAssessment(
            is_pattern=True,
            confidence=0.85,
            proposed_rule="Always handle errors",
            reasoning="Found in 5 files",
        )
        db.update_candidate_status("cand-1", CandidateStatus.INTERPRETED, llm_assessment=assessment)
        result = db.get_candidate("cand-1")
        assert result is not None
        assert result.llm_assessment is not None
        assert result.llm_assessment.is_pattern is True
        assert result.llm_assessment.confidence == 0.85


class TestSaveProposal:
    def test_save_and_get(self, db: LearningDatabase):
        db.save_proposal(_make_proposal())
        result = db.get_proposal("prop-1")
        assert result is not None
        assert result.id == "prop-1"
        assert result.title == "Error handling rule"
        assert result.confidence == 0.7

    def test_get_nonexistent_returns_none(self, db: LearningDatabase):
        assert db.get_proposal("nope") is None


class TestListProposals:
    def test_list_by_status(self, db: LearningDatabase):
        db.save_proposal(_make_proposal(id="p1", status=ProposalStatus.PENDING))
        db.save_proposal(_make_proposal(id="p2", status=ProposalStatus.ACCEPTED))
        db.save_proposal(_make_proposal(id="p3", status=ProposalStatus.PENDING))

        pending = db.list_proposals(status=ProposalStatus.PENDING)
        assert len(pending) == 2

    def test_list_by_min_confidence(self, db: LearningDatabase):
        db.save_proposal(_make_proposal(id="p1", confidence=0.3))
        db.save_proposal(_make_proposal(id="p2", confidence=0.9))

        results = db.list_proposals(min_confidence=0.5)
        assert len(results) == 1
        assert results[0].id == "p2"

    def test_list_with_limit(self, db: LearningDatabase):
        for i in range(10):
            db.save_proposal(_make_proposal(id=f"p{i}"))
        results = db.list_proposals(limit=5)
        assert len(results) == 5


class TestDecideProposal:
    def test_accept(self, db: LearningDatabase):
        db.save_proposal(_make_proposal())
        db.decide_proposal("prop-1", Decision.ACCEPT)
        result = db.get_proposal("prop-1")
        assert result is not None
        assert result.status == ProposalStatus.ACCEPTED
        assert result.decision == Decision.ACCEPT
        assert result.decided_at is not None

    def test_reject(self, db: LearningDatabase):
        db.save_proposal(_make_proposal())
        db.decide_proposal("prop-1", Decision.REJECT)
        result = db.get_proposal("prop-1")
        assert result is not None
        assert result.status == ProposalStatus.REJECTED

    def test_ignore(self, db: LearningDatabase):
        db.save_proposal(_make_proposal())
        db.decide_proposal("prop-1", Decision.IGNORE)
        result = db.get_proposal("prop-1")
        assert result is not None
        assert result.status == ProposalStatus.IGNORED

    def test_snooze(self, db: LearningDatabase):
        db.save_proposal(_make_proposal())
        db.decide_proposal("prop-1", Decision.SNOOZE)
        result = db.get_proposal("prop-1")
        assert result is not None
        assert result.status == ProposalStatus.SNOOZED

    def test_accept_with_edited_content(self, db: LearningDatabase):
        db.save_proposal(_make_proposal())
        db.decide_proposal("prop-1", Decision.ACCEPT, edited_content="Modified rule text")
        result = db.get_proposal("prop-1")
        assert result is not None
        assert result.edited_content == "Modified rule text"


class TestCountSessionProposals:
    def test_count_zero(self, db: LearningDatabase):
        assert db.count_session_proposals("sess-1") == 0

    def test_count_proposals(self, db: LearningDatabase):
        db.save_proposal(_make_proposal(id="p1", session_id="sess-1"))
        db.save_proposal(_make_proposal(id="p2", session_id="sess-1"))
        db.save_proposal(_make_proposal(id="p3", session_id="sess-2"))
        assert db.count_session_proposals("sess-1") == 2
        assert db.count_session_proposals("sess-2") == 1


class TestCooldown:
    def test_not_in_cooldown_fresh(self, db: LearningDatabase):
        assert db.is_in_cooldown(DetectionType.CODE_PATTERN, "hash1", cooldown_days=7) is False

    def test_in_cooldown_after_rejection(self, db: LearningDatabase):
        # Save a candidate and reject its proposal
        c = _make_candidate(description_hash="hash1")
        db.save_candidate(c)
        db.save_proposal(_make_proposal(candidate_id="cand-1"))
        db.decide_proposal("prop-1", Decision.REJECT)
        assert db.is_in_cooldown(DetectionType.CODE_PATTERN, "hash1", cooldown_days=7) is True

    def test_not_in_cooldown_after_expiry(self, db: LearningDatabase):
        c = _make_candidate(description_hash="hash1")
        db.save_candidate(c)
        db.save_proposal(_make_proposal(candidate_id="cand-1"))
        db.decide_proposal("prop-1", Decision.REJECT)
        # Manually set decided_at to 8 days ago
        old_date = (datetime.now(UTC) - timedelta(days=8)).isoformat()
        db._conn.execute(
            "UPDATE proposals SET decided_at = ? WHERE id = 'prop-1'", (old_date,)
        )
        db._conn.commit()
        assert db.is_in_cooldown(DetectionType.CODE_PATTERN, "hash1", cooldown_days=7) is False


class TestPriorDecisionFactor:
    def test_no_history_returns_1(self, db: LearningDatabase):
        assert db.get_prior_decision_factor(DetectionType.CODE_PATTERN) == 1.0

    def test_rejections_decrease_factor(self, db: LearningDatabase):
        c = _make_candidate()
        db.save_candidate(c)
        db.save_proposal(_make_proposal())
        db.decide_proposal("prop-1", Decision.REJECT)
        factor = db.get_prior_decision_factor(DetectionType.CODE_PATTERN)
        assert factor < 1.0

    def test_acceptances_increase_factor(self, db: LearningDatabase):
        c = _make_candidate()
        db.save_candidate(c)
        db.save_proposal(_make_proposal())
        db.decide_proposal("prop-1", Decision.ACCEPT)
        factor = db.get_prior_decision_factor(DetectionType.CODE_PATTERN)
        assert factor >= 1.0


class TestAnalysisState:
    def test_get_initial_state(self, db: LearningDatabase):
        state = db.get_analysis_state()
        assert state["last_commit"] is None
        assert state["total_commits_analyzed"] == 0

    def test_update_state(self, db: LearningDatabase):
        db.update_analysis_state("abc123", 10)
        state = db.get_analysis_state()
        assert state["last_commit"] == "abc123"
        assert state["total_commits_analyzed"] == 10

    def test_update_state_twice(self, db: LearningDatabase):
        db.update_analysis_state("abc123", 10)
        db.update_analysis_state("def456", 25)
        state = db.get_analysis_state()
        assert state["last_commit"] == "def456"
        assert state["total_commits_analyzed"] == 25


class TestStats:
    def test_empty_stats(self, db: LearningDatabase):
        s = db.stats()
        assert s["candidates_total"] == 0
        assert s["proposals_total"] == 0

    def test_stats_with_data(self, db: LearningDatabase):
        db.save_candidate(_make_candidate(id="c1"))
        db.save_candidate(_make_candidate(id="c2"))
        db.save_proposal(_make_proposal(id="p1"))

        s = db.stats()
        assert s["candidates_total"] == 2
        assert s["proposals_total"] == 1


class TestGetDbCreationTime:
    def test_returns_string(self, db: LearningDatabase):
        result = db.get_db_creation_time()
        assert result is not None
        assert isinstance(result, str)

    def test_format_is_iso(self, db: LearningDatabase):
        result = db.get_db_creation_time()
        assert result is not None
        # Should be parseable as ISO datetime
        from datetime import datetime
        datetime.fromisoformat(result)


class TestClose:
    def test_close_does_not_raise(self):
        db = LearningDatabase(":memory:")
        db.close()


class TestAnalyticsProperty:
    def test_analytics_returns_analytics_db(self):
        db = LearningDatabase(":memory:")
        from stratus.learning.analytics_db import AnalyticsDB
        assert isinstance(db.analytics, AnalyticsDB)
        db.close()
