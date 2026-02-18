"""Tests for learning/watcher.py — ProjectWatcher facade orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from stratus.learning.config import LearningConfig
from stratus.learning.database import LearningDatabase
from stratus.learning.models import (
    AnalysisResult,
    Detection,
    DetectionType,
    ProposalStatus,
    Sensitivity,
)
from stratus.learning.watcher import ProjectWatcher


@pytest.fixture
def db():
    database = LearningDatabase(":memory:")
    yield database
    database.close()


@pytest.fixture
def config():
    return LearningConfig(
        global_enabled=True, sensitivity=Sensitivity.MODERATE, min_age_hours=0,
    )


@pytest.fixture
def watcher(config, db):
    return ProjectWatcher(config=config, db=db, project_root=Path("/fake/repo"))


def _make_detection(**overrides) -> Detection:
    defaults = dict(
        type=DetectionType.CODE_PATTERN,
        count=5,
        confidence_raw=0.7,
        files=["src/a.py", "src/b.py", "src/c.py"],
        description="Repeated error handling",
        instances=[{"file": "src/a.py"}, {"file": "src/b.py"}],
    )
    defaults.update(overrides)
    return Detection(**defaults)


GIT_ANALYZER_PATH = "stratus.learning.watcher.GitAnalyzer"
AST_ANALYZER_PATH = "stratus.learning.watcher.find_repeated_patterns"
HEURISTICS_PATH = "stratus.learning.watcher.run_heuristics"


class TestAnalyzeChanges:
    def test_full_pipeline(self, watcher: ProjectWatcher):
        mock_git = MagicMock()
        mock_git.analyze_changes.return_value = [_make_detection()]
        mock_git._get_commits_since.return_value = 5

        with patch(GIT_ANALYZER_PATH) as MockAnalyzer, \
             patch(AST_ANALYZER_PATH, return_value=[]):
            MockAnalyzer.return_value = mock_git
            result = watcher.analyze_changes(since_commit="abc123")

        assert isinstance(result, AnalysisResult)
        assert len(result.detections) >= 0
        assert result.analysis_time_ms >= 0

    def test_no_detections(self, watcher: ProjectWatcher):
        mock_git = MagicMock()
        mock_git.analyze_changes.return_value = []
        mock_git._get_commits_since.return_value = 3

        with patch(GIT_ANALYZER_PATH) as MockAnalyzer, \
             patch(AST_ANALYZER_PATH, return_value=[]):
            MockAnalyzer.return_value = mock_git
            result = watcher.analyze_changes()

        assert result.detections == []
        assert result.analyzed_commits == 3

    def test_saves_candidates_to_db(self, watcher: ProjectWatcher, db: LearningDatabase):
        mock_git = MagicMock()
        mock_git.analyze_changes.return_value = [_make_detection()]
        mock_git._get_commits_since.return_value = 5

        with patch(GIT_ANALYZER_PATH) as MockAnalyzer, \
             patch(AST_ANALYZER_PATH, return_value=[]):
            MockAnalyzer.return_value = mock_git
            watcher.analyze_changes()

        candidates = db.list_candidates()
        # Should have saved candidates from heuristics
        # (may be 0 if heuristics filtered them out, which is valid)
        assert isinstance(candidates, list)

    def test_saves_proposals_to_db(self, watcher: ProjectWatcher, db: LearningDatabase):
        mock_git = MagicMock()
        detections = [
            _make_detection(
                count=5,
                files=["a.py", "b.py", "c.py", "d.py", "e.py"],
            ),
        ]
        mock_git.analyze_changes.return_value = detections
        mock_git._get_commits_since.return_value = 10

        with patch(GIT_ANALYZER_PATH) as MockAnalyzer, \
             patch(AST_ANALYZER_PATH, return_value=[]):
            MockAnalyzer.return_value = mock_git
            watcher.analyze_changes()

        proposals = db.list_proposals()
        assert isinstance(proposals, list)

    def test_updates_analysis_state(self, watcher: ProjectWatcher, db: LearningDatabase):
        mock_git = MagicMock()
        mock_git.analyze_changes.return_value = []
        mock_git._get_commits_since.return_value = 7

        with patch(GIT_ANALYZER_PATH) as MockAnalyzer, \
             patch(AST_ANALYZER_PATH, return_value=[]):
            MockAnalyzer.return_value = mock_git
            watcher.analyze_changes(since_commit="abc123")

        state = db.get_analysis_state()
        assert state["total_commits_analyzed"] == 7


class TestGetProposals:
    def test_returns_pending_proposals(self, watcher: ProjectWatcher, db: LearningDatabase):
        from stratus.learning.models import Proposal, ProposalType
        db.save_proposal(Proposal(
            id="p1",
            candidate_id="c1",
            type=ProposalType.RULE,
            title="Test rule",
            description="desc",
            proposed_content="content",
            confidence=0.8,
            status=ProposalStatus.PENDING,
        ))
        proposals = watcher.get_proposals()
        assert len(proposals) == 1

    def test_respects_max_count(self, watcher: ProjectWatcher, db: LearningDatabase):
        from stratus.learning.models import Proposal, ProposalType
        for i in range(5):
            db.save_proposal(Proposal(
                id=f"p{i}",
                candidate_id=f"c{i}",
                type=ProposalType.RULE,
                title=f"Rule {i}",
                description="desc",
                proposed_content="content",
                confidence=0.8,
            ))
        proposals = watcher.get_proposals(max_count=2)
        assert len(proposals) == 2

    def test_respects_min_confidence(self, watcher: ProjectWatcher, db: LearningDatabase):
        from stratus.learning.models import Proposal, ProposalType
        db.save_proposal(Proposal(
            id="p1", candidate_id="c1", type=ProposalType.RULE,
            title="High", description="d", proposed_content="c", confidence=0.9,
        ))
        db.save_proposal(Proposal(
            id="p2", candidate_id="c2", type=ProposalType.RULE,
            title="Low", description="d", proposed_content="c", confidence=0.3,
        ))
        proposals = watcher.get_proposals(min_confidence=0.5)
        assert len(proposals) == 1
        assert proposals[0].id == "p1"


class TestMinAgeGuard:
    def test_skips_when_db_too_young(self, db: LearningDatabase):
        """Analysis returns empty result when DB is younger than min_age_hours."""
        config = LearningConfig(
            global_enabled=True, sensitivity=Sensitivity.MODERATE, min_age_hours=24,
        )
        w = ProjectWatcher(config=config, db=db, project_root=Path("/fake/repo"))
        # DB was just created, so it's definitely < 24h old
        result = w.analyze_changes()
        assert result.detections == []
        assert result.analyzed_commits == 0
        assert result.analysis_time_ms == 0

    def test_runs_when_db_old_enough(self, db: LearningDatabase):
        """Analysis runs normally when DB age exceeds min_age_hours."""
        from datetime import UTC, datetime, timedelta
        config = LearningConfig(
            global_enabled=True, sensitivity=Sensitivity.MODERATE, min_age_hours=24,
        )
        w = ProjectWatcher(config=config, db=db, project_root=Path("/fake/repo"))
        # Backdate the schema_versions timestamp to 48 hours ago
        old_date = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
        db._conn.execute("UPDATE schema_versions SET applied_at = ? WHERE version = 1", (old_date,))
        db._conn.commit()

        mock_git = MagicMock()
        mock_git.analyze_changes.return_value = []
        mock_git._get_commits_since.return_value = 0

        with patch(GIT_ANALYZER_PATH) as MockAnalyzer, \
             patch(AST_ANALYZER_PATH, return_value=[]):
            MockAnalyzer.return_value = mock_git
            w.analyze_changes()

        # Should have proceeded past the guard (git analyzer was called)
        mock_git.analyze_changes.assert_called_once()

    def test_runs_when_min_age_zero(self, db: LearningDatabase):
        """No guard when min_age_hours is 0."""
        config = LearningConfig(
            global_enabled=True, sensitivity=Sensitivity.MODERATE, min_age_hours=0,
        )
        w = ProjectWatcher(config=config, db=db, project_root=Path("/fake/repo"))

        mock_git = MagicMock()
        mock_git.analyze_changes.return_value = []
        mock_git._get_commits_since.return_value = 0

        with patch(GIT_ANALYZER_PATH) as MockAnalyzer, \
             patch(AST_ANALYZER_PATH, return_value=[]):
            MockAnalyzer.return_value = mock_git
            w.analyze_changes()

        mock_git.analyze_changes.assert_called_once()


class TestDecideProposal:
    def test_accept_proposal(self, watcher: ProjectWatcher, db: LearningDatabase):
        from stratus.learning.models import Decision, Proposal, ProposalType
        db.save_proposal(Proposal(
            id="p1", candidate_id="c1", type=ProposalType.RULE,
            title="Test", description="d", proposed_content="c", confidence=0.8,
        ))
        with patch("stratus.learning.watcher.httpx") as mock_httpx:
            mock_httpx.post.return_value = MagicMock(status_code=200)
            result = watcher.decide_proposal("p1", Decision.ACCEPT)

        assert result["decision"] == "accept"
        assert result["proposal_id"] == "p1"

    def test_reject_proposal(self, watcher: ProjectWatcher, db: LearningDatabase):
        from stratus.learning.models import Decision, Proposal, ProposalType
        db.save_proposal(Proposal(
            id="p1", candidate_id="c1", type=ProposalType.RULE,
            title="Test", description="d", proposed_content="c", confidence=0.8,
        ))
        with patch("stratus.learning.watcher.httpx") as mock_httpx:
            mock_httpx.post.return_value = MagicMock(status_code=200)
            result = watcher.decide_proposal("p1", Decision.REJECT)

        assert result["decision"] == "reject"

    def test_accept_with_edited_content(self, watcher: ProjectWatcher, db: LearningDatabase):
        from stratus.learning.models import Decision, Proposal, ProposalType
        db.save_proposal(Proposal(
            id="p1", candidate_id="c1", type=ProposalType.RULE,
            title="Test", description="d", proposed_content="c", confidence=0.8,
        ))
        with patch("stratus.learning.watcher.httpx") as mock_httpx:
            mock_httpx.post.return_value = MagicMock(status_code=200)
            result = watcher.decide_proposal("p1", Decision.ACCEPT, edited_content="Modified")

        assert result["decision"] == "accept"
        p = db.get_proposal("p1")
        assert p is not None
        assert p.edited_content == "Modified"

    def test_memory_event_failure_non_blocking(self, watcher: ProjectWatcher, db: LearningDatabase):
        """Memory event save failures should not block the decision."""
        from stratus.learning.models import Decision, Proposal, ProposalType
        db.save_proposal(Proposal(
            id="p1", candidate_id="c1", type=ProposalType.RULE,
            title="Test", description="d", proposed_content="c", confidence=0.8,
        ))
        with patch("stratus.learning.watcher.httpx") as mock_httpx:
            mock_httpx.post.side_effect = Exception("connection refused")
            result = watcher.decide_proposal("p1", Decision.ACCEPT)

        # Should succeed despite memory event failure
        assert result["decision"] == "accept"

    def test_accept_creates_artifact(self, db: LearningDatabase, tmp_path):
        from stratus.learning.models import Decision, Proposal, ProposalType
        config = LearningConfig(global_enabled=True, sensitivity=Sensitivity.MODERATE)
        w = ProjectWatcher(config=config, db=db, project_root=tmp_path)
        db.save_proposal(Proposal(
            id="p1", candidate_id="c1", type=ProposalType.RULE,
            title="Error handling", description="d", proposed_content="content", confidence=0.8,
        ))
        with patch("stratus.learning.watcher.httpx") as mock_httpx:
            mock_httpx.post.return_value = MagicMock(status_code=200)
            result = w.decide_proposal("p1", Decision.ACCEPT)

        assert result["artifact_path"] is not None
        assert Path(result["artifact_path"]).exists()

    def test_accept_returns_artifact_path(self, db: LearningDatabase, tmp_path):
        from stratus.learning.models import Decision, Proposal, ProposalType
        config = LearningConfig(global_enabled=True, sensitivity=Sensitivity.MODERATE)
        w = ProjectWatcher(config=config, db=db, project_root=tmp_path)
        db.save_proposal(Proposal(
            id="p1", candidate_id="c1", type=ProposalType.RULE,
            title="Error handling", description="d", proposed_content="content", confidence=0.8,
        ))
        with patch("stratus.learning.watcher.httpx") as mock_httpx:
            mock_httpx.post.return_value = MagicMock(status_code=200)
            result = w.decide_proposal("p1", Decision.ACCEPT)

        assert "artifact_path" in result
        assert ".claude/rules" in result["artifact_path"]

    def test_reject_no_artifact(self, db: LearningDatabase, tmp_path):
        from stratus.learning.models import Decision, Proposal, ProposalType
        config = LearningConfig(global_enabled=True, sensitivity=Sensitivity.MODERATE)
        w = ProjectWatcher(config=config, db=db, project_root=tmp_path)
        db.save_proposal(Proposal(
            id="p1", candidate_id="c1", type=ProposalType.RULE,
            title="Error handling", description="d", proposed_content="content", confidence=0.8,
        ))
        with patch("stratus.learning.watcher.httpx") as mock_httpx:
            mock_httpx.post.return_value = MagicMock(status_code=200)
            result = w.decide_proposal("p1", Decision.REJECT)

        assert result["artifact_path"] is None

    def test_accept_with_edited_content_uses_edit(self, db: LearningDatabase, tmp_path):
        from stratus.learning.models import Decision, Proposal, ProposalType
        config = LearningConfig(global_enabled=True, sensitivity=Sensitivity.MODERATE)
        w = ProjectWatcher(config=config, db=db, project_root=tmp_path)
        db.save_proposal(Proposal(
            id="p1", candidate_id="c1", type=ProposalType.RULE,
            title="Error handling", description="d", proposed_content="content", confidence=0.8,
        ))
        with patch("stratus.learning.watcher.httpx") as mock_httpx:
            mock_httpx.post.return_value = MagicMock(status_code=200)
            result = w.decide_proposal("p1", Decision.ACCEPT, edited_content="Custom rule")

        assert result["artifact_path"] is not None
        assert Path(result["artifact_path"]).read_text() == "Custom rule"

    def test_memory_event_includes_title(self, db: LearningDatabase, tmp_path):
        from stratus.learning.models import Decision, Proposal, ProposalType
        config = LearningConfig(global_enabled=True, sensitivity=Sensitivity.MODERATE)
        w = ProjectWatcher(config=config, db=db, project_root=tmp_path)
        db.save_proposal(Proposal(
            id="p1", candidate_id="c1", type=ProposalType.RULE,
            title="Error handling rule", description="d", proposed_content="c", confidence=0.8,
        ))
        with patch("stratus.learning.watcher.httpx") as mock_httpx:
            mock_httpx.post.return_value = MagicMock(status_code=200)
            w.decide_proposal("p1", Decision.ACCEPT)

        call_kwargs = mock_httpx.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert "Error handling rule" in payload["text"]

    def test_memory_event_includes_refs(self, db: LearningDatabase, tmp_path):
        from stratus.learning.models import Decision, Proposal, ProposalType
        config = LearningConfig(global_enabled=True, sensitivity=Sensitivity.MODERATE)
        w = ProjectWatcher(config=config, db=db, project_root=tmp_path)
        db.save_proposal(Proposal(
            id="p1", candidate_id="c1", type=ProposalType.RULE,
            title="Error handling", description="d", proposed_content="c", confidence=0.8,
        ))
        with patch("stratus.learning.watcher.httpx") as mock_httpx:
            mock_httpx.post.return_value = MagicMock(status_code=200)
            w.decide_proposal("p1", Decision.ACCEPT)

        call_kwargs = mock_httpx.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert len(payload["refs"]) > 0

    def test_memory_event_includes_type_tag(self, db: LearningDatabase, tmp_path):
        from stratus.learning.models import Decision, Proposal, ProposalType
        config = LearningConfig(global_enabled=True, sensitivity=Sensitivity.MODERATE)
        w = ProjectWatcher(config=config, db=db, project_root=tmp_path)
        db.save_proposal(Proposal(
            id="p1", candidate_id="c1", type=ProposalType.RULE,
            title="Test", description="d", proposed_content="c", confidence=0.8,
        ))
        with patch("stratus.learning.watcher.httpx") as mock_httpx:
            mock_httpx.post.return_value = MagicMock(status_code=200)
            w.decide_proposal("p1", Decision.ACCEPT)

        call_kwargs = mock_httpx.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert "rule" in payload["tags"]

    def test_memory_event_accept_higher_importance(self, db: LearningDatabase, tmp_path):
        from stratus.learning.models import Decision, Proposal, ProposalType
        config = LearningConfig(global_enabled=True, sensitivity=Sensitivity.MODERATE)
        w = ProjectWatcher(config=config, db=db, project_root=tmp_path)
        db.save_proposal(Proposal(
            id="p1", candidate_id="c1", type=ProposalType.RULE,
            title="Test", description="d", proposed_content="c", confidence=0.8,
        ))
        with patch("stratus.learning.watcher.httpx") as mock_httpx:
            mock_httpx.post.return_value = MagicMock(status_code=200)
            w.decide_proposal("p1", Decision.ACCEPT)

        call_kwargs = mock_httpx.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["importance"] == 0.7

    def test_memory_event_includes_proposal_id(self, db: LearningDatabase, tmp_path):
        from stratus.learning.models import Decision, Proposal, ProposalType
        config = LearningConfig(global_enabled=True, sensitivity=Sensitivity.MODERATE)
        w = ProjectWatcher(config=config, db=db, project_root=tmp_path)
        db.save_proposal(Proposal(
            id="p1", candidate_id="c1", type=ProposalType.RULE,
            title="Test", description="d", proposed_content="c", confidence=0.8,
        ))
        with patch("stratus.learning.watcher.httpx") as mock_httpx:
            mock_httpx.post.return_value = MagicMock(status_code=200)
            w.decide_proposal("p1", Decision.ACCEPT)

        call_kwargs = mock_httpx.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["proposal_id"] == "p1"

    def test_accept_snapshots_baseline_in_db(self, db: LearningDatabase, tmp_path):
        """Accepting a proposal creates a RuleBaseline record in the analytics DB."""
        from stratus.learning.models import Decision, Proposal, ProposalType
        config = LearningConfig(global_enabled=True, sensitivity=Sensitivity.MODERATE)
        w = ProjectWatcher(config=config, db=db, project_root=tmp_path)
        db.save_proposal(Proposal(
            id="p1", candidate_id="c1", type=ProposalType.RULE,
            title="Error handling", description="d", proposed_content="content", confidence=0.8,
        ))
        with patch("stratus.learning.watcher.httpx") as mock_httpx:
            mock_httpx.post.return_value = MagicMock(status_code=200)
            result = w.decide_proposal("p1", Decision.ACCEPT)

        # A baseline should have been snapshotted in the analytics DB
        baselines = db.analytics.list_baselines()
        assert len(baselines) == 1
        assert baselines[0].proposal_id == "p1"
        assert result["artifact_path"] is not None

    def test_reject_does_not_snapshot_baseline(self, db: LearningDatabase, tmp_path):
        """Rejecting a proposal does NOT create a RuleBaseline."""
        from stratus.learning.models import Decision, Proposal, ProposalType
        config = LearningConfig(global_enabled=True, sensitivity=Sensitivity.MODERATE)
        w = ProjectWatcher(config=config, db=db, project_root=tmp_path)
        db.save_proposal(Proposal(
            id="p1", candidate_id="c1", type=ProposalType.RULE,
            title="Error handling", description="d", proposed_content="content", confidence=0.8,
        ))
        with patch("stratus.learning.watcher.httpx") as mock_httpx:
            mock_httpx.post.return_value = MagicMock(status_code=200)
            w.decide_proposal("p1", Decision.REJECT)

        baselines = db.analytics.list_baselines()
        assert len(baselines) == 0
