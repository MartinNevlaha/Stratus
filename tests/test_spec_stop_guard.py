"""Tests for spec_stop_guard hook."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest


def _write_spec_state(session_dir: Path, phase: str, hours_ago: float = 0.0) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    last_updated = (datetime.now(UTC) - timedelta(hours=hours_ago)).isoformat()
    data = {
        "phase": phase,
        "slug": "test-spec",
        "last_updated": last_updated,
    }
    (session_dir / "spec-state.json").write_text(json.dumps(data))


class TestSpecStopGuard:
    def test_exits_0_when_no_spec_state(self, tmp_path, monkeypatch):
        session_dir = tmp_path / "sessions" / "sess1"
        session_dir.mkdir(parents=True)
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "sess1")

        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.spec_stop_guard import main

            main()
        assert exc_info.value.code == 0

    def test_exits_0_when_phase_is_plan(self, tmp_path, monkeypatch):
        session_dir = tmp_path / "sessions" / "sess1"
        _write_spec_state(session_dir, "plan")
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "sess1")

        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.spec_stop_guard import main

            main()
        assert exc_info.value.code == 0

    def test_exits_0_when_phase_is_implement(self, tmp_path, monkeypatch):
        session_dir = tmp_path / "sessions" / "sess1"
        _write_spec_state(session_dir, "implement")
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "sess1")

        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.spec_stop_guard import main

            main()
        assert exc_info.value.code == 0

    def test_exits_0_when_phase_is_learn(self, tmp_path, monkeypatch):
        session_dir = tmp_path / "sessions" / "sess1"
        _write_spec_state(session_dir, "learn")
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "sess1")

        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.spec_stop_guard import main

            main()
        assert exc_info.value.code == 0

    def test_exits_2_when_phase_is_verify(self, tmp_path, monkeypatch):
        session_dir = tmp_path / "sessions" / "sess1"
        _write_spec_state(session_dir, "verify", hours_ago=0.1)
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "sess1")

        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.spec_stop_guard import main

            main()
        assert exc_info.value.code == 2

    def test_exits_0_when_verify_is_stale(self, tmp_path, monkeypatch):
        session_dir = tmp_path / "sessions" / "sess1"
        _write_spec_state(session_dir, "verify", hours_ago=5.0)
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "sess1")

        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.spec_stop_guard import main

            main()
        assert exc_info.value.code == 0

    def test_exits_2_when_verify_is_fresh(self, tmp_path, monkeypatch):
        session_dir = tmp_path / "sessions" / "sess1"
        _write_spec_state(session_dir, "verify", hours_ago=1.0)
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "sess1")

        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.spec_stop_guard import main

            main()
        assert exc_info.value.code == 2

    def test_exits_0_when_session_dir_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "nonexistent-session")

        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.spec_stop_guard import main

            main()
        assert exc_info.value.code == 0
