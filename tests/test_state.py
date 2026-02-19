"""Tests for session state management."""

from pathlib import Path

import pytest

from stratus.session.state import (
    read_state,
    resolve_session_id,
    write_state,
)


class TestResolveSessionId:
    def test_from_claude_code_task_list_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "task-abc")
        assert resolve_session_id() == "task-abc"

    def test_fallback_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CLAUDE_CODE_TASK_LIST_ID", raising=False)
        assert resolve_session_id() == "default"


class TestWriteAndReadState:
    def test_write_read_roundtrip(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        data = {"plan_file": "/path/to/plan.md", "tasks_done": 3}
        write_state(state_file, data)
        result = read_state(state_file)
        assert result == data

    def test_read_missing_file(self, tmp_path: Path) -> None:
        result = read_state(tmp_path / "nonexistent.json")
        assert result == {}

    def test_write_creates_parent_dirs(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "state.json"
        write_state(nested, {"key": "value"})
        assert nested.exists()
        result = read_state(nested)
        assert result == {"key": "value"}

    def test_overwrite_existing(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        write_state(state_file, {"v": 1})
        write_state(state_file, {"v": 2})
        result = read_state(state_file)
        assert result == {"v": 2}

    def test_read_corrupt_file(self, tmp_path: Path) -> None:
        state_file = tmp_path / "bad.json"
        _ = state_file.write_text("not valid json {{{")
        result = read_state(state_file)
        assert result == {}

    def test_write_no_tmp_files_left_behind(self, tmp_path: Path) -> None:
        """Atomic write leaves no .tmp files after successful write_state."""
        state_file = tmp_path / "state.json"
        write_state(state_file, {"key": "value"})
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == [], f"Unexpected .tmp files: {tmp_files}"

    def test_write_atomic_content_correct(self, tmp_path: Path) -> None:
        """Content written atomically matches the input data."""
        state_file = tmp_path / "state.json"
        data = {"session": "abc", "count": 42}
        write_state(state_file, data)
        import json
        result = json.loads(state_file.read_text())
        assert result == data
