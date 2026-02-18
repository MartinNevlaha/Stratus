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
        # Dir does not exist — should be created
        write_exit_log(session_dir, "new-sess")
        assert (session_dir / "exit-log.json").exists()


class TestSaveSessionSummary:
    def test_save_session_summary_calls_api(self, tmp_path):
        from stratus.hooks.session_end import save_session_summary

        session_dir = tmp_path / "sessions" / "sess1"
        mock_response = MagicMock()
        with patch("stratus.hooks.session_end.httpx") as mock_httpx:
            mock_httpx.post.return_value = mock_response
            save_session_summary(session_dir, "sess1")
        mock_httpx.post.assert_called_once()
        call_args = mock_httpx.post.call_args
        assert "/api/memory/save" in call_args.args[0]
        assert call_args.kwargs["json"]["session_id"] == "sess1"

    def test_save_session_summary_handles_failure(self, tmp_path):
        from stratus.hooks.session_end import save_session_summary

        session_dir = tmp_path / "sessions" / "sess1"
        with patch("stratus.hooks.session_end.httpx") as mock_httpx:
            mock_httpx.post.side_effect = Exception("connection refused")
            # Should not raise — best-effort
            save_session_summary(session_dir, "sess1")


class TestCleanupWorktreeStashes:
    def test_cleanup_worktree_stashes_no_git_root(self):
        from stratus.hooks.session_end import cleanup_worktree_stashes

        # Should be a no-op when git_root is None
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

        # First call: git stash list
        assert mock_run.call_args_list[0].args[0] == ["git", "stash", "list"]
        # Subsequent calls: git stash drop for matching entries
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
            # Should not raise — best-effort
            cleanup_worktree_stashes(tmp_path)


class TestMain:
    def test_main_exits_0(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "sess1")

        with (
            patch("stratus.hooks.session_end.httpx"),
            patch("stratus.hooks.session_end.subprocess"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                from stratus.hooks.session_end import main

                main()
        assert exc_info.value.code == 0

    def test_main_calls_all_cleanup_functions(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "sess1")

        with (
            patch("stratus.hooks.session_end.save_session_summary") as mock_save,
            patch(
                "stratus.hooks.session_end.cleanup_worktree_stashes"
            ) as mock_cleanup,
            patch("stratus.hooks.session_end.write_exit_log") as mock_log,
            patch(
                "stratus.hooks.session_end.get_git_root", return_value=None
            ),
        ):
            with pytest.raises(SystemExit):
                from stratus.hooks.session_end import main

                main()

        mock_save.assert_called_once()
        mock_cleanup.assert_called_once()
        mock_log.assert_called_once()
