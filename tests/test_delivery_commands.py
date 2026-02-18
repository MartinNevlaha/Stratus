"""Tests for orchestration/delivery_commands.py — CLI command handlers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pytest import CaptureFixture

from stratus.orchestration.delivery_models import (
    DeliveryPhase,
    DeliveryState,
)


def _make_state(phase: DeliveryPhase = DeliveryPhase.IMPLEMENTATION) -> DeliveryState:
    return DeliveryState(
        delivery_phase=phase,
        slug="test-feat",
        orchestration_mode="classic",
        active_roles=["backend-engineer"],
        phase_lead="tpm",
    )


@pytest.fixture
def session_dir(tmp_path: Path) -> Path:
    d = tmp_path / "sessions" / "default"
    d.mkdir(parents=True)
    return d


class TestCmdDeliveryStatus:
    def test_prints_json_state(self, session_dir: Path, capsys: CaptureFixture[str]) -> None:
        from stratus.orchestration.delivery_commands import cmd_delivery_status

        state = _make_state()
        with patch(
            "stratus.orchestration.delivery_commands.DeliveryCoordinator"
        ) as MockCoord:
            coord = MagicMock()
            coord.get_state.return_value = state
            MockCoord.return_value = coord
            cmd_delivery_status(session_dir)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["delivery_phase"] == "implementation"
        assert data["slug"] == "test-feat"

    def test_prints_no_active_when_state_is_none(
        self, session_dir: Path, capsys: CaptureFixture[str]
    ) -> None:
        from stratus.orchestration.delivery_commands import cmd_delivery_status

        with patch(
            "stratus.orchestration.delivery_commands.DeliveryCoordinator"
        ) as MockCoord:
            coord = MagicMock()
            coord.get_state.return_value = None
            MockCoord.return_value = coord
            cmd_delivery_status(session_dir)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["active"] is False


class TestCmdDeliveryStart:
    def test_starts_delivery_and_prints_state(
        self, session_dir: Path, capsys: CaptureFixture[str]
    ) -> None:
        from stratus.orchestration.delivery_commands import cmd_delivery_start

        state = _make_state(DeliveryPhase.IMPLEMENTATION)
        with patch(
            "stratus.orchestration.delivery_commands.DeliveryCoordinator"
        ) as MockCoord:
            coord = MagicMock()
            coord.start_delivery.return_value = state
            MockCoord.return_value = coord
            cmd_delivery_start(session_dir, slug="my-feat", mode="classic", plan_path=None)
            coord.start_delivery.assert_called_once_with(slug="my-feat", plan_path=None)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["slug"] == "test-feat"

    def test_start_with_plan_path(self, session_dir: Path) -> None:
        from stratus.orchestration.delivery_commands import cmd_delivery_start

        state = _make_state()
        with patch(
            "stratus.orchestration.delivery_commands.DeliveryCoordinator"
        ) as MockCoord:
            coord = MagicMock()
            coord.start_delivery.return_value = state
            MockCoord.return_value = coord
            cmd_delivery_start(session_dir, slug="feat", mode="swarm", plan_path="/plan.md")
            coord.start_delivery.assert_called_once_with(slug="feat", plan_path="/plan.md")

    def test_prints_error_on_value_error(
        self, session_dir: Path, capsys: CaptureFixture[str]
    ) -> None:
        from stratus.orchestration.delivery_commands import cmd_delivery_start

        with patch(
            "stratus.orchestration.delivery_commands.DeliveryCoordinator"
        ) as MockCoord:
            coord = MagicMock()
            coord.start_delivery.side_effect = ValueError("No active phases")
            MockCoord.return_value = coord
            with pytest.raises(SystemExit) as exc_info:
                cmd_delivery_start(session_dir, slug="feat", mode="classic", plan_path=None)
        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "No active phases" in err


class TestCmdDeliveryAdvance:
    def test_advances_phase_and_prints_state(
        self, session_dir: Path, capsys: CaptureFixture[str]
    ) -> None:
        from stratus.orchestration.delivery_commands import cmd_delivery_advance

        state = _make_state(DeliveryPhase.QA)
        with patch(
            "stratus.orchestration.delivery_commands.DeliveryCoordinator"
        ) as MockCoord:
            coord = MagicMock()
            coord.advance_phase.return_value = state
            MockCoord.return_value = coord
            cmd_delivery_advance(session_dir)
            coord.advance_phase.assert_called_once()

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["delivery_phase"] == "qa"

    def test_prints_error_when_no_next_phase(self, session_dir: Path) -> None:
        from stratus.orchestration.delivery_commands import cmd_delivery_advance

        with patch(
            "stratus.orchestration.delivery_commands.DeliveryCoordinator"
        ) as MockCoord:
            coord = MagicMock()
            coord.advance_phase.side_effect = ValueError("No next phase")
            MockCoord.return_value = coord
            with pytest.raises(SystemExit) as exc_info:
                cmd_delivery_advance(session_dir)
        assert exc_info.value.code == 1

    def test_prints_error_when_no_active_delivery(self, session_dir: Path) -> None:
        from stratus.orchestration.delivery_commands import cmd_delivery_advance

        with patch(
            "stratus.orchestration.delivery_commands.DeliveryCoordinator"
        ) as MockCoord:
            coord = MagicMock()
            coord.advance_phase.side_effect = RuntimeError("No active delivery")
            MockCoord.return_value = coord
            with pytest.raises(SystemExit) as exc_info:
                cmd_delivery_advance(session_dir)
        assert exc_info.value.code == 1


class TestCmdDeliverySkip:
    def test_skips_phase_and_prints_state(
        self, session_dir: Path, capsys: CaptureFixture[str]
    ) -> None:
        from stratus.orchestration.delivery_commands import cmd_delivery_skip

        state = _make_state(DeliveryPhase.QA)
        with patch(
            "stratus.orchestration.delivery_commands.DeliveryCoordinator"
        ) as MockCoord:
            coord = MagicMock()
            coord.skip_phase.return_value = state
            MockCoord.return_value = coord
            cmd_delivery_skip(session_dir, reason="Not needed")
            coord.skip_phase.assert_called_once_with("Not needed")

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["delivery_phase"] == "qa"

    def test_prints_error_on_failure(self, session_dir: Path, capsys: CaptureFixture[str]) -> None:
        from stratus.orchestration.delivery_commands import cmd_delivery_skip

        with patch(
            "stratus.orchestration.delivery_commands.DeliveryCoordinator"
        ) as MockCoord:
            coord = MagicMock()
            coord.skip_phase.side_effect = ValueError("No phase to skip to")
            MockCoord.return_value = coord
            with pytest.raises(SystemExit) as exc_info:
                cmd_delivery_skip(session_dir, reason="reason")
        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "No phase to skip to" in err
