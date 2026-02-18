"""Tests for hooks/learning_trigger.py — PostToolUse hook for git commands."""

from __future__ import annotations

import json
from unittest.mock import patch

from stratus.hooks.learning_trigger import (
    is_git_commit_command,
    main,
    should_trigger_analysis,
)


class TestIsGitCommitCommand:
    def test_git_commit(self):
        assert is_git_commit_command("git commit -m 'test'") is True

    def test_git_merge(self):
        assert is_git_commit_command("git merge feature-branch") is True

    def test_git_pull(self):
        assert is_git_commit_command("git pull origin main") is True

    def test_git_status_not_commit(self):
        assert is_git_commit_command("git status") is False

    def test_git_diff_not_commit(self):
        assert is_git_commit_command("git diff") is False

    def test_empty_command(self):
        assert is_git_commit_command("") is False

    def test_non_git_command(self):
        assert is_git_commit_command("npm install") is False

    def test_git_in_pipe(self):
        assert is_git_commit_command("echo test | git commit") is True


class TestShouldTriggerAnalysis:
    def test_below_threshold(self, tmp_path):
        state_file = tmp_path / "learning-state.json"
        state_file.write_text(json.dumps({"commit_count": 2}))
        assert should_trigger_analysis(state_file, threshold=5) is False

    def test_at_threshold(self, tmp_path):
        state_file = tmp_path / "learning-state.json"
        state_file.write_text(json.dumps({"commit_count": 4}))
        assert should_trigger_analysis(state_file, threshold=5) is True

    def test_no_state_file(self, tmp_path):
        state_file = tmp_path / "learning-state.json"
        assert should_trigger_analysis(state_file, threshold=5) is False

    def test_resets_after_trigger(self, tmp_path):
        state_file = tmp_path / "learning-state.json"
        state_file.write_text(json.dumps({"commit_count": 5}))
        should_trigger_analysis(state_file, threshold=5)
        data = json.loads(state_file.read_text())
        assert data["commit_count"] == 0


class TestMain:
    def test_non_bash_tool_exits_0(self):
        with patch("sys.stdin") as mock_stdin, \
             patch("sys.exit") as mock_exit:
            mock_stdin.read.return_value = json.dumps({
                "tool_name": "Read",
                "tool_input": {"file_path": "/test"},
            })
            main()
            mock_exit.assert_called_with(0)

    def test_bash_non_git_exits_0(self):
        with patch("sys.stdin") as mock_stdin, \
             patch("sys.exit") as mock_exit:
            mock_stdin.read.return_value = json.dumps({
                "tool_name": "Bash",
                "tool_input": {"command": "npm install"},
            })
            main()
            mock_exit.assert_called_with(0)

    def test_bash_git_commit_increments_counter(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        state_file = tmp_path / "learning-state.json"
        state_file.write_text(json.dumps({"commit_count": 0}))

        with patch("sys.stdin") as mock_stdin, \
             patch("sys.exit"):
            mock_stdin.read.return_value = json.dumps({
                "tool_name": "Bash",
                "tool_input": {"command": "git commit -m 'test'"},
            })
            main()

        data = json.loads(state_file.read_text())
        assert data["commit_count"] == 1

    def test_empty_stdin_exits_0(self):
        with patch("sys.stdin") as mock_stdin, \
             patch("sys.exit") as mock_exit:
            mock_stdin.read.return_value = ""
            main()
            mock_exit.assert_called_with(0)

    def test_global_disabled_exits_0(self, tmp_path, monkeypatch):
        """When learning is disabled, should not process anything."""
        monkeypatch.setenv("AI_FRAMEWORK_LEARNING_ENABLED", "false")
        with patch("sys.stdin") as mock_stdin, \
             patch("sys.exit") as mock_exit:
            mock_stdin.read.return_value = json.dumps({
                "tool_name": "Bash",
                "tool_input": {"command": "git commit -m 'test'"},
            })
            main()
            mock_exit.assert_called_with(0)
