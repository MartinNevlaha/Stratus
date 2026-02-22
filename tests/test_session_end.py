"""Tests for session_end hook."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


class TestWriteExitLog:
    def test_write_exit_log_creates_file(self, tmp_path):
        from stratus.hooks.session_end import write_exit_log

        session_dir = tmp_path / "sessions" / "sess1"
        session_dir.mkdir(parents=True)
        write_exit_log(session_dir, "sess1")
        assert (session_dir / "exit-log.json").exists()

    def test_write_exit_log_contains_timestamp(self, tmp_path):
        from stratus.hooks.session_end import write_exit_log

        session_dir = tmp_path / "sessions" / "sess1"
        session_dir.mkdir(parents=True)
        write_exit_log(session_dir, "sess1")
        data = json.loads((session_dir / "exit-log.json").read_text())
        assert "exited_at" in data
        assert data["session_id"] == "sess1"

    def test_write_exit_log_handles_missing_dir(self, tmp_path):
        from stratus.hooks.session_end import write_exit_log

        session_dir = tmp_path / "sessions" / "new-sess"
        write_exit_log(session_dir, "new-sess")
        assert (session_dir / "exit-log.json").exists()


class TestCleanupWorktreeStashes:
    def test_cleanup_worktree_stashes_no_git_root(self):
        from stratus.hooks.session_end import cleanup_worktree_stashes

        cleanup_worktree_stashes(None)

    def test_cleanup_worktree_stashes_removes_matching(self, tmp_path):
        from stratus.hooks.session_end import cleanup_worktree_stashes

        stash_list_output = (
            "stash@{0}: ai-framework: save work\n"
            "stash@{1}: WIP on main: abc123 some commit\n"
            "stash@{2}: ai-framework: another save\n"
        )
        list_result = MagicMock()
        list_result.returncode = 0
        list_result.stdout = stash_list_output

        drop_result = MagicMock()
        drop_result.returncode = 0

        with patch(
            "stratus.hooks.session_end.subprocess.run",
            side_effect=[list_result, drop_result, drop_result],
        ) as mock_run:
            cleanup_worktree_stashes(tmp_path)

        assert mock_run.call_args_list[0].args[0] == ["git", "stash", "list"]
        drop_calls = mock_run.call_args_list[1:]
        assert len(drop_calls) == 2
        for c in drop_calls:
            assert c.args[0][0] == "git"
            assert c.args[0][1] == "stash"
            assert c.args[0][2] == "drop"

    def test_cleanup_worktree_stashes_ignores_errors(self, tmp_path):
        from stratus.hooks.session_end import cleanup_worktree_stashes

        with patch(
            "stratus.hooks.session_end.subprocess.run",
            side_effect=Exception("git crashed"),
        ):
            cleanup_worktree_stashes(tmp_path)


class TestCleanupWorktreeStashesCorrectIndices:
    def test_drops_stashes_in_reverse_index_order(self, tmp_path):
        """C1: drop highest matching index first so lower indices don't shift."""
        from stratus.hooks.session_end import cleanup_worktree_stashes

        stash_list_output = (
            "stash@{0}: ai-framework: save work\n"
            "stash@{1}: WIP on main: abc123 some commit\n"
            "stash@{2}: ai-framework: another save\n"
        )
        list_result = MagicMock()
        list_result.returncode = 0
        list_result.stdout = stash_list_output

        drop_result = MagicMock()
        drop_result.returncode = 0

        with patch(
            "stratus.hooks.session_end.subprocess.run",
            side_effect=[list_result, drop_result, drop_result],
        ) as mock_run:
            cleanup_worktree_stashes(tmp_path)

        drop_calls = mock_run.call_args_list[1:]
        assert len(drop_calls) == 2
        first_drop_arg = drop_calls[0].args[0][3]
        second_drop_arg = drop_calls[1].args[0][3]
        assert first_drop_arg == "stash@{2}", (
            f"Expected stash@{{2}} to be dropped first, got {first_drop_arg}"
        )
        assert second_drop_arg == "stash@{0}", (
            f"Expected stash@{{0}} to be dropped second, got {second_drop_arg}"
        )

    def test_does_not_drop_wrong_index_when_only_last_matches(self, tmp_path):
        """C1: When only the last stash matches, drop stash@{2} not stash@{0}."""
        from stratus.hooks.session_end import cleanup_worktree_stashes

        stash_list_output = (
            "stash@{0}: WIP on main: normal work\n"
            "stash@{1}: WIP on main: more work\n"
            "stash@{2}: ai-framework: our stash\n"
        )
        list_result = MagicMock()
        list_result.returncode = 0
        list_result.stdout = stash_list_output

        drop_result = MagicMock()
        drop_result.returncode = 0

        with patch(
            "stratus.hooks.session_end.subprocess.run",
            side_effect=[list_result, drop_result],
        ) as mock_run:
            cleanup_worktree_stashes(tmp_path)

        drop_calls = mock_run.call_args_list[1:]
        assert len(drop_calls) == 1
        dropped = drop_calls[0].args[0][3]
        assert dropped == "stash@{2}", (
            f"Bug C1: wrong stash dropped — expected stash@{{2}}, got {dropped}"
        )


class TestWriteExitLogAtomic:
    def test_write_exit_log_is_atomic(self, tmp_path):
        """C2: write_exit_log must use atomic write (os.replace) not direct write_text."""
        import os

        from stratus.hooks.session_end import write_exit_log

        session_dir = tmp_path / "sessions" / "sess1"
        session_dir.mkdir(parents=True)

        replace_calls: list[tuple[object, object]] = []
        real_replace = os.replace

        def tracking_replace(src: object, dst: object) -> None:
            replace_calls.append((src, dst))
            real_replace(src, dst)  # type: ignore[arg-type]

        with patch("os.replace", side_effect=tracking_replace):
            write_exit_log(session_dir, "sess1")

        assert (session_dir / "exit-log.json").exists(), "exit-log.json not created"
        final_path = session_dir / "exit-log.json"
        replaced_destinations = [str(dst) for _, dst in replace_calls]
        assert str(final_path) in replaced_destinations, (
            f"C2: os.replace was not called with {final_path}. "
            f"Bug: write_text used instead of atomic write."
        )


class TestMain:
    def test_main_exits_0(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "sess1")

        with patch("stratus.hooks.session_end.subprocess"):
            with pytest.raises(SystemExit) as exc_info:
                from stratus.hooks.session_end import main

                main()
        assert exc_info.value.code == 0

    def test_main_calls_all_cleanup_functions(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "sess1")

        with (
            patch("stratus.hooks.session_end.cleanup_worktree_stashes") as mock_cleanup,
            patch("stratus.hooks.session_end.write_exit_log") as mock_log,
            patch("stratus.hooks.session_end.get_git_root", return_value=None),
        ):
            with pytest.raises(SystemExit):
                from stratus.hooks.session_end import main

                main()

        mock_cleanup.assert_called_once()
        mock_log.assert_called_once()
