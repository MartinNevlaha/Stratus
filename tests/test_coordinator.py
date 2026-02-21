"""Tests for orchestration/coordinator.py — SpecCoordinator state machine."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from stratus.orchestration.coordinator import SpecCoordinator
from stratus.orchestration.models import (
    FindingSeverity,
    PlanStatus,
    ReviewFinding,
    ReviewVerdict,
    SpecPhase,
    Verdict,
)


@pytest.fixture
def session_dir(tmp_path: Path) -> Path:
    d = tmp_path / "sessions" / "test-session"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def coordinator(session_dir: Path, tmp_path: Path) -> SpecCoordinator:
    return SpecCoordinator(
        session_dir=session_dir,
        project_root=tmp_path,
        api_url="http://127.0.0.1:41777",
    )


# ---------------------------------------------------------------------------
# Lifecycle: start_spec
# ---------------------------------------------------------------------------


class TestStartSpec:
    def test_creates_initial_state(self, coordinator: SpecCoordinator):
        state = coordinator.start_spec("my-feature", plan_path="/plan.md")
        assert state.phase == SpecPhase.PLAN
        assert state.slug == "my-feature"
        assert state.plan_path == "/plan.md"
        assert state.plan_status == PlanStatus.PENDING

    def test_persists_state_to_disk(self, coordinator: SpecCoordinator, session_dir: Path):
        coordinator.start_spec("feat")
        path = session_dir / "spec-state.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["slug"] == "feat"

    def test_raises_if_spec_already_active(self, coordinator: SpecCoordinator):
        coordinator.start_spec("feat")
        with pytest.raises(ValueError, match="already active"):
            coordinator.start_spec("feat2")


class TestGetState:
    def test_returns_none_when_no_spec(self, coordinator: SpecCoordinator):
        assert coordinator.get_state() is None

    def test_returns_current_state(self, coordinator: SpecCoordinator):
        coordinator.start_spec("feat")
        state = coordinator.get_state()
        assert state is not None
        assert state.slug == "feat"


# ---------------------------------------------------------------------------
# Plan phase
# ---------------------------------------------------------------------------


class TestApprovePlan:
    def test_transitions_to_implement(self, coordinator: SpecCoordinator):
        coordinator.start_spec("feat")
        state = coordinator.approve_plan(total_tasks=5)
        assert state.phase == SpecPhase.IMPLEMENT
        assert state.plan_status == PlanStatus.APPROVED
        assert state.total_tasks == 5
        assert state.current_task == 1

    def test_raises_if_not_in_plan_phase(self, coordinator: SpecCoordinator):
        coordinator.start_spec("feat")
        coordinator.approve_plan(total_tasks=3)
        with pytest.raises(ValueError, match="not in plan phase"):
            coordinator.approve_plan(total_tasks=3)


# ---------------------------------------------------------------------------
# Implement phase
# ---------------------------------------------------------------------------


class TestTaskManagement:
    def test_start_task_updates_current(self, coordinator: SpecCoordinator):
        coordinator.start_spec("feat")
        coordinator.approve_plan(total_tasks=3)
        state = coordinator.start_task(2)
        assert state.current_task == 2

    def test_complete_task_increments_completed(self, coordinator: SpecCoordinator):
        coordinator.start_spec("feat")
        coordinator.approve_plan(total_tasks=3)
        state = coordinator.complete_task(1)
        assert state.completed_tasks == 1

    def test_all_tasks_done_false(self, coordinator: SpecCoordinator):
        coordinator.start_spec("feat")
        coordinator.approve_plan(total_tasks=3)
        assert coordinator.all_tasks_done() is False

    def test_all_tasks_done_true(self, coordinator: SpecCoordinator):
        coordinator.start_spec("feat")
        coordinator.approve_plan(total_tasks=2)
        coordinator.complete_task(1)
        coordinator.complete_task(2)
        assert coordinator.all_tasks_done() is True


# ---------------------------------------------------------------------------
# Verify phase
# ---------------------------------------------------------------------------


class TestVerifyPhase:
    def test_start_verify_transitions(self, coordinator: SpecCoordinator):
        coordinator.start_spec("feat")
        coordinator.approve_plan(total_tasks=1)
        coordinator.complete_task(1)
        state = coordinator.start_verify()
        assert state.phase == SpecPhase.VERIFY
        assert state.plan_status == PlanStatus.VERIFYING

    def test_record_verdicts_all_pass(self, coordinator: SpecCoordinator):
        coordinator.start_spec("feat")
        coordinator.approve_plan(total_tasks=1)
        coordinator.complete_task(1)
        coordinator.start_verify()
        v = ReviewVerdict(reviewer="compliance", verdict=Verdict.PASS, findings=[], raw_output="")
        result = coordinator.record_verdicts([v])
        assert result["all_passed"] is True

    def test_record_verdicts_with_failure(self, coordinator: SpecCoordinator):
        coordinator.start_spec("feat")
        coordinator.approve_plan(total_tasks=1)
        coordinator.complete_task(1)
        coordinator.start_verify()
        v = ReviewVerdict(reviewer="quality", verdict=Verdict.FAIL, findings=[], raw_output="")
        result = coordinator.record_verdicts([v])
        assert result["all_passed"] is False
        assert "quality" in result["failed_reviewers"]

    def test_needs_fix_loop_after_failure(self, coordinator: SpecCoordinator):
        coordinator.start_spec("feat")
        coordinator.approve_plan(total_tasks=1)
        coordinator.complete_task(1)
        coordinator.start_verify()
        v = ReviewVerdict(reviewer="q", verdict=Verdict.FAIL, findings=[], raw_output="")
        coordinator.record_verdicts([v])
        assert coordinator.needs_fix_loop() is True

    def test_no_fix_loop_after_pass(self, coordinator: SpecCoordinator):
        coordinator.start_spec("feat")
        coordinator.approve_plan(total_tasks=1)
        coordinator.complete_task(1)
        coordinator.start_verify()
        v = ReviewVerdict(reviewer="q", verdict=Verdict.PASS, findings=[], raw_output="")
        coordinator.record_verdicts([v])
        assert coordinator.needs_fix_loop() is False

    def test_start_fix_loop_transitions_back_to_implement(self, coordinator: SpecCoordinator):
        coordinator.start_spec("feat")
        coordinator.approve_plan(total_tasks=1)
        coordinator.complete_task(1)
        coordinator.start_verify()
        v = ReviewVerdict(reviewer="q", verdict=Verdict.FAIL, findings=[], raw_output="")
        coordinator.record_verdicts([v])
        state = coordinator.start_fix_loop()
        assert state.phase == SpecPhase.IMPLEMENT
        assert state.review_iteration == 1

    def test_fix_loop_limited_by_max_iterations(self, coordinator: SpecCoordinator):
        coordinator.start_spec("feat")
        coordinator.approve_plan(total_tasks=1)
        coordinator.complete_task(1)

        # Exhaust all 3 review iterations (max_review_iterations=3)
        for i in range(3):
            coordinator.start_verify()
            v = ReviewVerdict(reviewer="q", verdict=Verdict.FAIL, findings=[], raw_output="")
            coordinator.record_verdicts([v])
            coordinator.start_fix_loop()  # increments review_iteration

        # After 3 fix loops, review_iteration=3 which equals max, so no more
        coordinator.start_verify()
        v = ReviewVerdict(reviewer="q", verdict=Verdict.FAIL, findings=[], raw_output="")
        coordinator.record_verdicts([v])
        assert coordinator.needs_fix_loop() is False


# ---------------------------------------------------------------------------
# Learn phase
# ---------------------------------------------------------------------------


class TestLearnPhase:
    def test_start_learn_from_verify(self, coordinator: SpecCoordinator):
        coordinator.start_spec("feat")
        coordinator.approve_plan(total_tasks=1)
        coordinator.complete_task(1)
        coordinator.start_verify()
        v = ReviewVerdict(reviewer="q", verdict=Verdict.PASS, findings=[], raw_output="")
        coordinator.record_verdicts([v])
        state = coordinator.start_learn()
        assert state.phase == SpecPhase.LEARN

    def test_complete_spec(self, coordinator: SpecCoordinator):
        coordinator.start_spec("feat")
        coordinator.approve_plan(total_tasks=1)
        coordinator.complete_task(1)
        coordinator.start_verify()
        v = ReviewVerdict(reviewer="q", verdict=Verdict.PASS, findings=[], raw_output="")
        coordinator.record_verdicts([v])
        coordinator.start_learn()
        state = coordinator.complete_spec()
        assert state.phase == SpecPhase.COMPLETE
        assert state.plan_status == PlanStatus.COMPLETE

    def test_can_start_new_spec_after_complete(self, coordinator: SpecCoordinator):
        coordinator.start_spec("feat")
        coordinator.approve_plan(total_tasks=1)
        coordinator.complete_task(1)
        coordinator.start_verify()
        v = ReviewVerdict(reviewer="q", verdict=Verdict.PASS, findings=[], raw_output="")
        coordinator.record_verdicts([v])
        coordinator.start_learn()
        coordinator.complete_spec()
        state = coordinator.start_spec("new-feature")
        assert state.slug == "new-feature"
        assert state.phase == SpecPhase.PLAN


# ---------------------------------------------------------------------------
# Worktree integration
# ---------------------------------------------------------------------------


class TestWorktreeIntegration:
    @patch("stratus.orchestration.coordinator.worktree")
    def test_setup_worktree(self, mock_wt, coordinator: SpecCoordinator):
        mock_wt.create.return_value = {
            "path": "/tmp/wt",
            "branch": "spec/feat",
            "base_branch": "main",
            "stashed": False,
        }
        coordinator.start_spec("feat", plan_path="/plan.md")
        info = coordinator.setup_worktree()
        assert info.slug == "feat"
        assert info.branch == "spec/feat"

    @patch("stratus.orchestration.coordinator.worktree")
    def test_sync_worktree(self, mock_wt, coordinator: SpecCoordinator):
        mock_wt.create.return_value = {
            "path": "/tmp/wt",
            "branch": "spec/feat",
            "base_branch": "main",
            "stashed": False,
        }
        mock_wt.sync.return_value = {
            "merged": True,
            "commit": "abc",
            "files_changed": 3,
            "insertions": 10,
            "deletions": 2,
        }
        coordinator.start_spec("feat")
        coordinator.setup_worktree()
        result = coordinator.sync_worktree()
        assert result["merged"] is True

    @patch("stratus.orchestration.coordinator.worktree")
    def test_cleanup_worktree(self, mock_wt, coordinator: SpecCoordinator):
        mock_wt.create.return_value = {
            "path": "/tmp/wt",
            "branch": "spec/feat",
            "base_branch": "main",
            "stashed": False,
        }
        mock_wt.cleanup.return_value = {
            "removed": True,
            "path": "/tmp/wt",
            "branch_deleted": True,
        }
        coordinator.start_spec("feat")
        coordinator.setup_worktree()
        result = coordinator.cleanup_worktree()
        assert result["removed"] is True


# ---------------------------------------------------------------------------
# Memory events (best-effort HTTP)
# ---------------------------------------------------------------------------


class TestMemoryEvents:
    @patch("stratus.orchestration.coordinator.httpx")
    def test_memory_event_sent_on_start(self, mock_httpx, coordinator):
        mock_client = MagicMock()
        mock_httpx.Client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_httpx.Client.return_value.__exit__ = MagicMock(return_value=False)
        coordinator.start_spec("feat")
        mock_client.post.assert_called_once()

    @patch("stratus.orchestration.coordinator.httpx")
    def test_memory_event_failure_does_not_raise(self, mock_httpx, coordinator):
        mock_client = MagicMock()
        mock_client.post.side_effect = Exception("network error")
        mock_httpx.Client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_httpx.Client.return_value.__exit__ = MagicMock(return_value=False)
        state = coordinator.start_spec("feat")
        assert state.phase == SpecPhase.PLAN  # didn't raise


class TestReviewFailureRecording:
    @patch("stratus.orchestration.coordinator.httpx")
    def test_record_review_failures_called_on_fail_verdict(self, mock_httpx, coordinator):
        """record_verdicts calls _record_review_failures which posts for each failed reviewer."""
        mock_client = MagicMock()
        mock_httpx.Client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_httpx.Client.return_value.__exit__ = MagicMock(return_value=False)

        coordinator.start_spec("feat")
        coordinator.approve_plan(total_tasks=1)
        coordinator.complete_task(1)
        coordinator.start_verify()

        finding = ReviewFinding(
            severity=FindingSeverity.MUST_FIX,
            description="Missing docstring",
            file_path="src/foo.py",
        )
        v = ReviewVerdict(
            reviewer="quality",
            verdict=Verdict.FAIL,
            findings=[finding],
            raw_output="",
        )
        coordinator.record_verdicts([v])

        # httpx.post should have been called for the failing verdict
        mock_httpx.post.assert_called_once()
        call_kwargs = mock_httpx.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["category"] == "review_failure"
        assert "quality" in payload["detail"]
        assert "Missing docstring" in payload["detail"]

    @patch("stratus.orchestration.coordinator.httpx")
    def test_record_review_failures_not_called_on_pass(self, mock_httpx, coordinator):
        """record_verdicts does NOT post analytics when all verdicts pass."""
        mock_client = MagicMock()
        mock_httpx.Client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_httpx.Client.return_value.__exit__ = MagicMock(return_value=False)

        coordinator.start_spec("feat")
        coordinator.approve_plan(total_tasks=1)
        coordinator.complete_task(1)
        coordinator.start_verify()

        v = ReviewVerdict(
            reviewer="quality",
            verdict=Verdict.PASS,
            findings=[],
            raw_output="",
        )
        coordinator.record_verdicts([v])

        mock_httpx.post.assert_not_called()

    @patch("stratus.orchestration.coordinator.httpx")
    def test_review_failure_recording_non_blocking(self, mock_httpx, coordinator):
        """Failure recording exceptions do not block record_verdicts."""
        mock_client = MagicMock()
        mock_httpx.Client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_httpx.Client.return_value.__exit__ = MagicMock(return_value=False)
        mock_httpx.post.side_effect = Exception("network error")

        coordinator.start_spec("feat")
        coordinator.approve_plan(total_tasks=1)
        coordinator.complete_task(1)
        coordinator.start_verify()

        v = ReviewVerdict(reviewer="q", verdict=Verdict.FAIL, findings=[], raw_output="")
        # Must not raise
        result = coordinator.record_verdicts([v])
        assert result["all_passed"] is False
