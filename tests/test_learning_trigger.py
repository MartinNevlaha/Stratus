"""Tests for hooks/learning_trigger.py — PostToolUse hook for git commands."""

from __future__ import annotations

import json
from unittest.mock import patch

from stratus.hooks.learning_trigger import (
    _increment_commit_count,
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

    def test_no_tmp_files_left_after_trigger(self, tmp_path):
        """Atomic write leaves no .tmp files after should_trigger_analysis resets counter."""
        state_file = tmp_path / "learning-state.json"
        state_file.write_text(json.dumps({"commit_count": 4}))
        should_trigger_analysis(state_file, threshold=5)
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == [], f"Unexpected .tmp files: {tmp_files}"


class TestIncrementCommitCount:
    def test_increments_existing_count(self, tmp_path):
        state_file = tmp_path / "learning-state.json"
        state_file.write_text(json.dumps({"commit_count": 3}))
        _increment_commit_count(state_file)
        data = json.loads(state_file.read_text())
        assert data["commit_count"] == 4

    def test_initializes_missing_file(self, tmp_path):
        state_file = tmp_path / "learning-state.json"
        _increment_commit_count(state_file)
        data = json.loads(state_file.read_text())
        assert data["commit_count"] == 1

    def test_no_tmp_files_left_after_increment(self, tmp_path):
        """Atomic write leaves no .tmp files after _increment_commit_count."""
        state_file = tmp_path / "learning-state.json"
        state_file.write_text(json.dumps({"commit_count": 0}))
        _increment_commit_count(state_file)
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == [], f"Unexpected .tmp files: {tmp_files}"


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
        (tmp_path / ".ai-framework.json").write_text("{}")

        with patch("sys.stdin") as mock_stdin, \
             patch("sys.exit"), \
             patch("httpx.post"), \
             patch("stratus.hooks.learning_trigger.get_git_root", return_value=tmp_path):
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
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        (tmp_path / ".ai-framework.json").write_text("{}")
        with patch("sys.stdin") as mock_stdin, \
             patch("sys.exit") as mock_exit, \
             patch("httpx.post"), \
             patch("stratus.hooks.learning_trigger.get_git_root", return_value=tmp_path):
            mock_stdin.read.return_value = json.dumps({
                "tool_name": "Bash",
                "tool_input": {"command": "git commit -m 'test'"},
            })
            main()
            mock_exit.assert_called_with(0)

    def test_bash_git_commit_fires_reindex_post(self, tmp_path, monkeypatch):
        """Reindex POST is always fired on git commit regardless of learning config."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        state_file = tmp_path / "learning-state.json"
        state_file.write_text(json.dumps({"commit_count": 0}))
        (tmp_path / ".ai-framework.json").write_text("{}")

        with patch("sys.stdin") as mock_stdin, \
             patch("sys.exit"), \
             patch("httpx.post") as mock_post, \
             patch("stratus.hooks.learning_trigger.get_git_root", return_value=tmp_path):
            mock_stdin.read.return_value = json.dumps({
                "tool_name": "Bash",
                "tool_input": {"command": "git commit -m 'test'"},
            })
            main()

        urls = [str(call.args[0]) for call in mock_post.call_args_list]
        assert any("/api/retrieval/index" in url for url in urls)

    def test_reindex_fires_even_when_learning_disabled(self, tmp_path, monkeypatch):
        """Reindex fires even when AI_FRAMEWORK_LEARNING_ENABLED=false."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("AI_FRAMEWORK_LEARNING_ENABLED", "false")

        with patch("sys.stdin") as mock_stdin, \
             patch("sys.exit"), \
             patch("httpx.post") as mock_post, \
             patch("stratus.hooks.learning_trigger.get_git_root", return_value=tmp_path):
            (tmp_path / ".ai-framework.json").write_text("{}")
            mock_stdin.read.return_value = json.dumps({
                "tool_name": "Bash",
                "tool_input": {"command": "git commit -m 'test'"},
            })
            main()

        urls = [str(call.args[0]) for call in mock_post.call_args_list]
        assert any("/api/retrieval/index" in url for url in urls)


class TestStratusInitGuard:
    """Fix 2: learning_trigger must check for .ai-framework.json before firing."""

    def test_main_exits_early_if_no_ai_framework_json(self, tmp_path, monkeypatch):
        """No POST to /api/retrieval/index when .ai-framework.json is absent."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))

        with patch("sys.stdin") as mock_stdin, \
             patch("sys.exit"), \
             patch("httpx.post") as mock_post, \
             patch("stratus.hooks.learning_trigger.get_git_root", return_value=tmp_path):
            # .ai-framework.json does NOT exist in tmp_path
            mock_stdin.read.return_value = json.dumps({
                "tool_name": "Bash",
                "tool_input": {"command": "git commit -m 'test'"},
            })
            main()

        urls = [str(call.args[0]) for call in mock_post.call_args_list]
        assert not any("/api/retrieval/index" in url for url in urls)

    def test_main_fires_reindex_if_ai_framework_json_exists(self, tmp_path, monkeypatch):
        """POST to /api/retrieval/index fires when .ai-framework.json is present."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        (tmp_path / ".ai-framework.json").write_text("{}")

        with patch("sys.stdin") as mock_stdin, \
             patch("sys.exit"), \
             patch("httpx.post") as mock_post, \
             patch("stratus.hooks.learning_trigger.get_git_root", return_value=tmp_path):
            mock_stdin.read.return_value = json.dumps({
                "tool_name": "Bash",
                "tool_input": {"command": "git commit -m 'test'"},
            })
            main()

        urls = [str(call.args[0]) for call in mock_post.call_args_list]
        assert any("/api/retrieval/index" in url for url in urls)
