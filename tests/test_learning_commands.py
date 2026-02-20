# pyright: basic
"""Unit tests for learning/commands.py — cmd_learning action branches."""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest

from stratus.learning.models import (
    AnalysisResult,
    Decision,
    Detection,
    DetectionType,
    Proposal,
    ProposalStatus,
    ProposalType,
    Sensitivity,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_args(**kwargs: object) -> argparse.Namespace:
    """Return a Namespace with defaults merged with overrides."""
    defaults: dict[str, object] = {
        "learning_action": "status",
        "since": None,
        "scope": None,
        "max_count": 10,
        "min_confidence": 0.0,
        "proposal_id": None,
        "decision": None,
        "enable": False,
        "disable": False,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _make_config(
    *,
    global_enabled: bool = False,
    sensitivity: Sensitivity = Sensitivity.CONSERVATIVE,
    min_confidence: float = 0.7,
    cooldown_days: int = 7,
    max_proposals_per_session: int = 3,
    batch_frequency: str = "session_end",
    commit_batch_threshold: int = 5,
    min_age_hours: int = 24,
) -> MagicMock:
    cfg: MagicMock = MagicMock()
    cfg.global_enabled = global_enabled
    cfg.sensitivity = sensitivity
    cfg.min_confidence = min_confidence
    cfg.cooldown_days = cooldown_days
    cfg.max_proposals_per_session = max_proposals_per_session
    cfg.batch_frequency = batch_frequency
    cfg.commit_batch_threshold = commit_batch_threshold
    cfg.min_age_hours = min_age_hours
    return cfg


def _make_db_mock(
    *,
    stats: dict[str, object] | None = None,
    analysis_state: dict[str, object] | None = None,
    proposals: list[Proposal] | None = None,
) -> MagicMock:
    db: MagicMock = MagicMock()
    db.stats.return_value = stats or {"candidates_total": 0, "proposals_total": 0}
    db.get_analysis_state.return_value = analysis_state or {
        "last_commit": None,
        "total_commits_analyzed": 0,
    }
    db.list_proposals.return_value = proposals or []
    return db


# Patch paths — all imports happen inside cmd_learning(), so patch at the
# module level where they are resolved (inside stratus.learning.*).
_CONFIG_PATH = "stratus.learning.config.load_learning_config"
_DB_PATH = "stratus.learning.database.LearningDatabase"
_WATCHER_PATH = "stratus.learning.watcher.ProjectWatcher"


# ---------------------------------------------------------------------------
# TestCmdLearningStatus
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCmdLearningStatus:
    def test_status_prints_config_and_stats(self, capsys: pytest.CaptureFixture[str]) -> None:
        config = _make_config(global_enabled=True, sensitivity=Sensitivity.MODERATE)
        db_mock = _make_db_mock(
            stats={"candidates_total": 5, "proposals_total": 3},
            analysis_state={"last_commit": "abc123", "total_commits_analyzed": 12},
        )

        with patch(_CONFIG_PATH, return_value=config), patch(_DB_PATH, return_value=db_mock):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="status"))

        out = capsys.readouterr().out
        assert "Learning Status" in out
        assert "Enabled" in out
        assert "Sensitivity" in out
        assert "Candidates" in out
        assert "Proposals" in out

    def test_status_shows_enabled_value(self, capsys: pytest.CaptureFixture[str]) -> None:
        config = _make_config(global_enabled=True)
        db_mock = _make_db_mock()

        with patch(_CONFIG_PATH, return_value=config), patch(_DB_PATH, return_value=db_mock):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="status"))

        out = capsys.readouterr().out
        assert "True" in out

    def test_status_shows_last_commit(self, capsys: pytest.CaptureFixture[str]) -> None:
        config = _make_config()
        db_mock = _make_db_mock(
            analysis_state={"last_commit": "deadbeef", "total_commits_analyzed": 7},
        )

        with patch(_CONFIG_PATH, return_value=config), patch(_DB_PATH, return_value=db_mock):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="status"))

        out = capsys.readouterr().out
        assert "deadbeef" in out
        assert "7" in out

    def test_status_calls_db_close(self) -> None:
        config = _make_config()
        db_mock = _make_db_mock()

        with patch(_CONFIG_PATH, return_value=config), patch(_DB_PATH, return_value=db_mock):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="status"))

        db_mock.close.assert_called_once()


# ---------------------------------------------------------------------------
# TestCmdLearningAnalyze
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCmdLearningAnalyze:
    def _make_analysis_result(
        self,
        *,
        detections: list[Detection] | None = None,
        analyzed_commits: int = 4,
        analysis_time_ms: int = 120,
    ) -> AnalysisResult:
        if detections is None:
            detections = [
                Detection(
                    type=DetectionType.CODE_PATTERN,
                    count=3,
                    confidence_raw=0.75,
                    files=["a.py", "b.py", "c.py"],
                    description="Repeated error handling",
                )
            ]
        return AnalysisResult(
            detections=detections,
            analyzed_commits=analyzed_commits,
            analysis_time_ms=analysis_time_ms,
        )

    def test_analyze_prints_results(self, capsys: pytest.CaptureFixture[str]) -> None:
        config = _make_config()
        db_mock = _make_db_mock()
        result = self._make_analysis_result(analyzed_commits=4, analysis_time_ms=120)
        watcher_mock = MagicMock()
        watcher_mock.analyze_changes.return_value = result

        with (
            patch(_CONFIG_PATH, return_value=config),
            patch(_DB_PATH, return_value=db_mock),
            patch(_WATCHER_PATH, return_value=watcher_mock),
        ):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="analyze"))

        out = capsys.readouterr().out
        assert "Detections" in out
        assert "Commits" in out
        assert "Time" in out

    def test_analyze_shows_detection_count(self, capsys: pytest.CaptureFixture[str]) -> None:
        config = _make_config()
        db_mock = _make_db_mock()
        result = self._make_analysis_result(analyzed_commits=6, analysis_time_ms=50)
        watcher_mock = MagicMock()
        watcher_mock.analyze_changes.return_value = result

        with (
            patch(_CONFIG_PATH, return_value=config),
            patch(_DB_PATH, return_value=db_mock),
            patch(_WATCHER_PATH, return_value=watcher_mock),
        ):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="analyze"))

        out = capsys.readouterr().out
        # 1 detection was created in _make_analysis_result
        assert "1" in out
        assert "6" in out
        assert "50" in out

    def test_analyze_passes_since_commit(self) -> None:
        config = _make_config()
        db_mock = _make_db_mock()
        result = self._make_analysis_result(detections=[], analyzed_commits=0, analysis_time_ms=0)
        watcher_mock = MagicMock()
        watcher_mock.analyze_changes.return_value = result

        with (
            patch(_CONFIG_PATH, return_value=config),
            patch(_DB_PATH, return_value=db_mock),
            patch(_WATCHER_PATH, return_value=watcher_mock),
        ):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="analyze", since="abc123"))

        watcher_mock.analyze_changes.assert_called_once_with(since_commit="abc123", scope=None)

    def test_analyze_passes_scope(self) -> None:
        config = _make_config()
        db_mock = _make_db_mock()
        result = self._make_analysis_result(detections=[], analyzed_commits=0, analysis_time_ms=0)
        watcher_mock = MagicMock()
        watcher_mock.analyze_changes.return_value = result

        with (
            patch(_CONFIG_PATH, return_value=config),
            patch(_DB_PATH, return_value=db_mock),
            patch(_WATCHER_PATH, return_value=watcher_mock),
        ):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="analyze", scope="src/"))

        watcher_mock.analyze_changes.assert_called_once_with(since_commit=None, scope="src/")

    def test_analyze_calls_db_close(self) -> None:
        config = _make_config()
        db_mock = _make_db_mock()
        result = self._make_analysis_result(detections=[], analyzed_commits=0, analysis_time_ms=0)
        watcher_mock = MagicMock()
        watcher_mock.analyze_changes.return_value = result

        with (
            patch(_CONFIG_PATH, return_value=config),
            patch(_DB_PATH, return_value=db_mock),
            patch(_WATCHER_PATH, return_value=watcher_mock),
        ):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="analyze"))

        db_mock.close.assert_called_once()


# ---------------------------------------------------------------------------
# TestCmdLearningProposals
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCmdLearningProposals:
    def _make_proposal(self, pid: str = "abcdef12-1234-5678-abcd-123456789012") -> Proposal:
        return Proposal(
            id=pid,
            candidate_id="cand-1",
            type=ProposalType.RULE,
            title="Use consistent error handling",
            description="Always wrap external calls with try/except",
            proposed_content="## Rule\nWrap all external calls.",
            confidence=0.85,
            status=ProposalStatus.PENDING,
        )

    def test_proposals_lists_pending(self, capsys: pytest.CaptureFixture[str]) -> None:
        proposal = self._make_proposal("abcdef12-1234-5678-abcd-123456789012")
        config = _make_config()
        db_mock = _make_db_mock(proposals=[proposal])

        with patch(_CONFIG_PATH, return_value=config), patch(_DB_PATH, return_value=db_mock):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="proposals"))

        out = capsys.readouterr().out
        # ID is truncated to first 8 chars in the output
        assert "abcdef12" in out
        assert "Use consistent error handling" in out

    def test_proposals_empty(self, capsys: pytest.CaptureFixture[str]) -> None:
        config = _make_config()
        db_mock = _make_db_mock(proposals=[])

        with patch(_CONFIG_PATH, return_value=config), patch(_DB_PATH, return_value=db_mock):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="proposals"))

        out = capsys.readouterr().out
        assert "No pending proposals" in out

    def test_proposals_passes_min_confidence(self) -> None:
        config = _make_config()
        db_mock = _make_db_mock(proposals=[])

        with patch(_CONFIG_PATH, return_value=config), patch(_DB_PATH, return_value=db_mock):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="proposals", min_confidence=0.6))

        db_mock.list_proposals.assert_called_once_with(
            status=ProposalStatus.PENDING,
            min_confidence=0.6,
            limit=10,
        )

    def test_proposals_passes_max_count(self) -> None:
        config = _make_config()
        db_mock = _make_db_mock(proposals=[])

        with patch(_CONFIG_PATH, return_value=config), patch(_DB_PATH, return_value=db_mock):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="proposals", max_count=5))

        db_mock.list_proposals.assert_called_once_with(
            status=ProposalStatus.PENDING,
            min_confidence=0.0,
            limit=5,
        )

    def test_proposals_shows_confidence(self, capsys: pytest.CaptureFixture[str]) -> None:
        proposal = self._make_proposal()
        config = _make_config()
        db_mock = _make_db_mock(proposals=[proposal])

        with patch(_CONFIG_PATH, return_value=config), patch(_DB_PATH, return_value=db_mock):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="proposals"))

        out = capsys.readouterr().out
        assert "0.85" in out

    def test_proposals_calls_db_close(self) -> None:
        config = _make_config()
        db_mock = _make_db_mock(proposals=[])

        with patch(_CONFIG_PATH, return_value=config), patch(_DB_PATH, return_value=db_mock):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="proposals"))

        db_mock.close.assert_called_once()


# ---------------------------------------------------------------------------
# TestCmdLearningDecide
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCmdLearningDecide:
    def test_decide_calls_watcher(self) -> None:
        config = _make_config()
        db_mock = _make_db_mock()
        watcher_mock = MagicMock()
        watcher_mock.decide_proposal.return_value = {
            "proposal_id": "some-uuid-1234",
            "decision": "accept",
            "artifact_path": None,
        }

        with (
            patch(_CONFIG_PATH, return_value=config),
            patch(_DB_PATH, return_value=db_mock),
            patch(_WATCHER_PATH, return_value=watcher_mock),
        ):
            from stratus.learning.commands import cmd_learning

            cmd_learning(
                _make_args(
                    learning_action="decide",
                    proposal_id="some-uuid-1234",
                    decision="accept",
                )
            )

        watcher_mock.decide_proposal.assert_called_once_with("some-uuid-1234", Decision.ACCEPT)

    def test_decide_reject_calls_watcher(self) -> None:
        config = _make_config()
        db_mock = _make_db_mock()
        watcher_mock = MagicMock()
        watcher_mock.decide_proposal.return_value = {
            "proposal_id": "pid-xyz",
            "decision": "reject",
            "artifact_path": None,
        }

        with (
            patch(_CONFIG_PATH, return_value=config),
            patch(_DB_PATH, return_value=db_mock),
            patch(_WATCHER_PATH, return_value=watcher_mock),
        ):
            from stratus.learning.commands import cmd_learning

            cmd_learning(
                _make_args(
                    learning_action="decide",
                    proposal_id="pid-xyz",
                    decision="reject",
                )
            )

        watcher_mock.decide_proposal.assert_called_once_with("pid-xyz", Decision.REJECT)

    def test_decide_prints_decided(self, capsys: pytest.CaptureFixture[str]) -> None:
        config = _make_config()
        db_mock = _make_db_mock()
        watcher_mock = MagicMock()
        watcher_mock.decide_proposal.return_value = {
            "proposal_id": "pid-abc",
            "decision": "accept",
            "artifact_path": None,
        }

        with (
            patch(_CONFIG_PATH, return_value=config),
            patch(_DB_PATH, return_value=db_mock),
            patch(_WATCHER_PATH, return_value=watcher_mock),
        ):
            from stratus.learning.commands import cmd_learning

            cmd_learning(
                _make_args(
                    learning_action="decide",
                    proposal_id="pid-abc",
                    decision="accept",
                )
            )

        out = capsys.readouterr().out
        assert "Decided" in out
        assert "pid-abc" in out
        assert "accept" in out

    def test_decide_ignore(self, capsys: pytest.CaptureFixture[str]) -> None:
        config = _make_config()
        db_mock = _make_db_mock()
        watcher_mock = MagicMock()
        watcher_mock.decide_proposal.return_value = {
            "proposal_id": "pid-ignore",
            "decision": "ignore",
            "artifact_path": None,
        }

        with (
            patch(_CONFIG_PATH, return_value=config),
            patch(_DB_PATH, return_value=db_mock),
            patch(_WATCHER_PATH, return_value=watcher_mock),
        ):
            from stratus.learning.commands import cmd_learning

            cmd_learning(
                _make_args(
                    learning_action="decide",
                    proposal_id="pid-ignore",
                    decision="ignore",
                )
            )

        watcher_mock.decide_proposal.assert_called_once_with("pid-ignore", Decision.IGNORE)
        out = capsys.readouterr().out
        assert "ignore" in out

    def test_decide_accept_shows_artifact_path(self, capsys: pytest.CaptureFixture[str]) -> None:
        config = _make_config()
        db_mock = _make_db_mock()
        watcher_mock = MagicMock()
        watcher_mock.decide_proposal.return_value = {
            "proposal_id": "pid-artifact",
            "decision": "accept",
            "artifact_path": "/path/to/.claude/rules/new-rule.md",
        }

        with (
            patch(_CONFIG_PATH, return_value=config),
            patch(_DB_PATH, return_value=db_mock),
            patch(_WATCHER_PATH, return_value=watcher_mock),
        ):
            from stratus.learning.commands import cmd_learning

            cmd_learning(
                _make_args(
                    learning_action="decide",
                    proposal_id="pid-artifact",
                    decision="accept",
                )
            )

        out = capsys.readouterr().out
        assert "Created" in out
        assert "/path/to/.claude/rules/new-rule.md" in out

    def test_decide_calls_db_close(self) -> None:
        config = _make_config()
        db_mock = _make_db_mock()
        watcher_mock = MagicMock()
        watcher_mock.decide_proposal.return_value = {
            "proposal_id": "pid",
            "decision": "accept",
            "artifact_path": None,
        }

        with (
            patch(_CONFIG_PATH, return_value=config),
            patch(_DB_PATH, return_value=db_mock),
            patch(_WATCHER_PATH, return_value=watcher_mock),
        ):
            from stratus.learning.commands import cmd_learning

            cmd_learning(
                _make_args(
                    learning_action="decide",
                    proposal_id="pid",
                    decision="accept",
                )
            )

        db_mock.close.assert_called_once()


# ---------------------------------------------------------------------------
# TestCmdLearningConfig
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCmdLearningConfig:
    def test_config_prints_settings(self, capsys: pytest.CaptureFixture[str]) -> None:
        config = _make_config(
            global_enabled=True,
            sensitivity=Sensitivity.MODERATE,
            min_confidence=0.5,
            cooldown_days=14,
            max_proposals_per_session=5,
            batch_frequency="commit",
            commit_batch_threshold=3,
            min_age_hours=48,
        )
        db_mock = _make_db_mock()

        with patch(_CONFIG_PATH, return_value=config), patch(_DB_PATH, return_value=db_mock):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="config"))

        out = capsys.readouterr().out
        assert "global_enabled" in out
        assert "sensitivity" in out
        assert "min_confidence" in out
        assert "cooldown_days" in out

    def test_config_shows_correct_values(self, capsys: pytest.CaptureFixture[str]) -> None:
        config = _make_config(
            global_enabled=False,
            sensitivity=Sensitivity.AGGRESSIVE,
            cooldown_days=3,
            max_proposals_per_session=7,
        )
        db_mock = _make_db_mock()

        with patch(_CONFIG_PATH, return_value=config), patch(_DB_PATH, return_value=db_mock):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="config"))

        out = capsys.readouterr().out
        assert "False" in out
        assert str(Sensitivity.AGGRESSIVE) in out
        assert "3" in out

    def test_config_enable_flag_prints_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        config = _make_config()
        db_mock = _make_db_mock()

        with patch(_CONFIG_PATH, return_value=config), patch(_DB_PATH, return_value=db_mock):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="config", enable=True))

        out = capsys.readouterr().out
        assert "enabled" in out.lower()

    def test_config_disable_flag_prints_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        config = _make_config()
        db_mock = _make_db_mock()

        with patch(_CONFIG_PATH, return_value=config), patch(_DB_PATH, return_value=db_mock):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="config", disable=True))

        out = capsys.readouterr().out
        assert "disabled" in out.lower()

    def test_config_shows_batch_frequency(self, capsys: pytest.CaptureFixture[str]) -> None:
        config = _make_config(batch_frequency="commit")
        db_mock = _make_db_mock()

        with patch(_CONFIG_PATH, return_value=config), patch(_DB_PATH, return_value=db_mock):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="config"))

        out = capsys.readouterr().out
        assert "batch_frequency" in out
        assert "commit" in out

    def test_config_shows_commit_threshold(self, capsys: pytest.CaptureFixture[str]) -> None:
        config = _make_config(commit_batch_threshold=8)
        db_mock = _make_db_mock()

        with patch(_CONFIG_PATH, return_value=config), patch(_DB_PATH, return_value=db_mock):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="config"))

        out = capsys.readouterr().out
        assert "commit_threshold" in out
        assert "8" in out

    def test_config_shows_min_age_hours(self, capsys: pytest.CaptureFixture[str]) -> None:
        config = _make_config(min_age_hours=72)
        db_mock = _make_db_mock()

        with patch(_CONFIG_PATH, return_value=config), patch(_DB_PATH, return_value=db_mock):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="config"))

        out = capsys.readouterr().out
        assert "min_age_hours" in out
        assert "72" in out

    def test_config_calls_db_close(self) -> None:
        config = _make_config()
        db_mock = _make_db_mock()

        with patch(_CONFIG_PATH, return_value=config), patch(_DB_PATH, return_value=db_mock):
            from stratus.learning.commands import cmd_learning

            cmd_learning(_make_args(learning_action="config"))

        db_mock.close.assert_called_once()
