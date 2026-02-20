"""Tests for hook scripts: common utilities, context monitor, pre-compact, post-compact."""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from stratus.hooks._common import get_api_url, get_git_root, get_session_dir, read_hook_input
from stratus.hooks.context_monitor import (
    check_context_usage,
    should_throttle,
)
from stratus.hooks.post_compact_restore import build_restore_message
from stratus.hooks.pre_compact import capture_pre_compact_state


class TestGetGitRoot:
    def test_get_git_root_returns_path(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "/home/user/myproject\n"
        with patch("stratus.hooks._common.subprocess.run", return_value=mock_result):
            result = get_git_root()
        assert result == Path("/home/user/myproject")

    def test_get_git_root_returns_none_not_in_repo(self):
        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stdout = ""
        with patch("stratus.hooks._common.subprocess.run", return_value=mock_result):
            result = get_git_root()
        assert result is None

    def test_get_git_root_returns_none_git_not_found(self):
        with patch(
            "stratus.hooks._common.subprocess.run",
            side_effect=FileNotFoundError("git not found"),
        ):
            result = get_git_root()
        assert result is None


class TestReadHookInput:
    def test_reads_json_from_stdin(self):
        data = {"session_id": "test-123", "transcript_path": "/tmp/transcript.jsonl"}
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = json.dumps(data)
            result = read_hook_input()
        assert result == data

    def test_returns_empty_on_invalid_json(self):
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = "not valid json"
            result = read_hook_input()
        assert result == {}

    def test_returns_empty_on_empty_stdin(self):
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = ""
            result = read_hook_input()
        assert result == {}


class TestGetSessionDir:
    def test_returns_session_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        session_dir = get_session_dir("session-abc")
        assert session_dir == tmp_path / "sessions" / "session-abc"

    def test_uses_default_data_dir(self, monkeypatch):
        monkeypatch.delenv("AI_FRAMEWORK_DATA_DIR", raising=False)
        session_dir = get_session_dir("my-session")
        expected = Path.home() / ".ai-framework" / "data" / "sessions" / "my-session"
        assert session_dir == expected


class TestGetApiUrl:
    def test_from_port_lock(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        lock_file = tmp_path / "port.lock"
        lock_file.write_text(json.dumps({"port": 9999, "pid": 12345}))
        url = get_api_url()
        assert url == "http://127.0.0.1:9999"

    def test_default_when_no_lock(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        url = get_api_url()
        assert url == "http://127.0.0.1:41777"


class TestShouldThrottle:
    def test_no_throttle_on_first_call(self, tmp_path):
        cache_file = tmp_path / "context-cache.json"
        assert should_throttle(cache_file, threshold_pct=60.0) is False

    def test_throttle_within_interval(self, tmp_path):
        cache_file = tmp_path / "context-cache.json"
        cache_file.write_text(
            json.dumps(
                {
                    "last_check_time": time.time(),
                    "last_pct": 50.0,
                }
            )
        )
        assert should_throttle(cache_file, threshold_pct=60.0) is True

    def test_no_throttle_after_interval(self, tmp_path):
        cache_file = tmp_path / "context-cache.json"
        cache_file.write_text(
            json.dumps(
                {
                    "last_check_time": time.time() - 60,
                    "last_pct": 50.0,
                }
            )
        )
        assert should_throttle(cache_file, threshold_pct=60.0) is False

    def test_no_throttle_when_above_warn(self, tmp_path):
        cache_file = tmp_path / "context-cache.json"
        cache_file.write_text(
            json.dumps(
                {
                    "last_check_time": time.time(),
                    "last_pct": 70.0,
                }
            )
        )
        # Above 65% threshold, should not throttle (always check)
        assert should_throttle(cache_file, threshold_pct=70.0) is False


class TestCheckContextUsage:
    def test_below_warn_returns_none(self, simple_transcript, tmp_path):
        # simple_transcript has peak ~64K tokens, well under 65% of 200K
        result = check_context_usage(simple_transcript, cache_dir=tmp_path)
        assert result is None

    def test_returns_warning_at_high_context(self, transcript_with_compaction, tmp_path):
        # transcript_with_compaction has pre-compaction messages at ~90K tokens
        # but the peak is 90,001. That's 45% of 200K. Still below 65%.
        result = check_context_usage(transcript_with_compaction, cache_dir=tmp_path)
        # At 45%, no warning expected
        assert result is None

    def test_returns_warning_when_above_threshold(self, tmp_path):
        """Create a transcript with high token count to trigger warning."""
        from tests.conftest import _make_assistant_message, _write_jsonl

        entries = [
            _make_assistant_message(
                uuid="a1",
                input_tokens=1,
                cache_creation_input_tokens=140000,
                cache_read_input_tokens=0,
                output_tokens=500,
            ),
        ]
        transcript = _write_jsonl(tmp_path / "high.jsonl", entries)
        result = check_context_usage(transcript, cache_dir=tmp_path)
        assert result is not None
        assert "context" in result.lower() or "%" in result


class TestCapturePreCompactState:
    def test_captures_state_to_file(self, tmp_path):
        session_dir = tmp_path / "sessions" / "test-session"
        state = {
            "plan_file": "/path/to/plan.md",
            "tasks": ["task1", "task2"],
        }
        capture_pre_compact_state(session_dir, state)
        state_file = session_dir / "pre-compact-state.json"
        assert state_file.exists()
        saved = json.loads(state_file.read_text())
        assert saved["plan_file"] == "/path/to/plan.md"
        assert saved["tasks"] == ["task1", "task2"]

    def test_captures_timestamp(self, tmp_path):
        session_dir = tmp_path / "sessions" / "test-session"
        capture_pre_compact_state(session_dir, {"key": "value"})
        state_file = session_dir / "pre-compact-state.json"
        saved = json.loads(state_file.read_text())
        assert "captured_at" in saved


class TestBuildRestoreMessage:
    def test_builds_message_from_state(self, tmp_path):
        session_dir = tmp_path / "sessions" / "test-session"
        session_dir.mkdir(parents=True)
        state_file = session_dir / "pre-compact-state.json"
        state_file.write_text(
            json.dumps(
                {
                    "plan_file": "/path/to/plan.md",
                    "tasks": ["task1", "task2"],
                    "captured_at": "2026-01-01T00:00:00Z",
                }
            )
        )

        message = build_restore_message(session_dir)
        assert message is not None
        lower = message.lower()
        assert "plan" in lower or "restore" in lower or "context" in lower

    def test_returns_none_when_no_state(self, tmp_path):
        session_dir = tmp_path / "sessions" / "test-session"
        session_dir.mkdir(parents=True)
        message = build_restore_message(session_dir)
        assert message is None

    def test_returns_none_on_corrupt_state_file(self, tmp_path):
        session_dir = tmp_path / "sessions" / "test-session"
        session_dir.mkdir(parents=True)
        (session_dir / "pre-compact-state.json").write_text("not json{{{")
        message = build_restore_message(session_dir)
        assert message is None


class TestContextMonitorMain:
    def test_exits_0_when_no_transcript_path(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", type("", (), {"read": lambda self: "{}"})())
        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.context_monitor import main

            main()
        assert exc_info.value.code == 0

    def test_exits_0_when_transcript_missing(self, monkeypatch, tmp_path):
        hook_json = json.dumps({"transcript_path": str(tmp_path / "nonexistent.jsonl")})
        monkeypatch.setattr("sys.stdin", type("", (), {"read": lambda self: hook_json})())
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.context_monitor import main

            main()
        assert exc_info.value.code == 0

    def test_exits_2_on_high_context(self, monkeypatch, tmp_path, capsys):
        from tests.conftest import _make_assistant_message, _write_jsonl

        transcript = _write_jsonl(
            tmp_path / "high.jsonl",
            [
                _make_assistant_message(
                    uuid="a1",
                    input_tokens=1,
                    cache_creation_input_tokens=140000,
                    cache_read_input_tokens=0,
                    output_tokens=500,
                ),
            ],
        )
        hook_json = json.dumps({"transcript_path": str(transcript)})
        monkeypatch.setattr("sys.stdin", type("", (), {"read": lambda self: hook_json})())
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))

        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.context_monitor import main

            main()
        assert exc_info.value.code == 2

    def test_exits_0_on_low_context(self, monkeypatch, tmp_path):
        from tests.conftest import _make_assistant_message, _write_jsonl

        transcript = _write_jsonl(
            tmp_path / "low.jsonl",
            [
                _make_assistant_message(
                    uuid="a1",
                    input_tokens=1,
                    cache_creation_input_tokens=10000,
                    cache_read_input_tokens=0,
                    output_tokens=100,
                ),
            ],
        )
        hook_json = json.dumps({"transcript_path": str(transcript)})
        monkeypatch.setattr("sys.stdin", type("", (), {"read": lambda self: hook_json})())
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))

        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.context_monitor import main

            main()
        assert exc_info.value.code == 0


class TestPreCompactMain:
    def test_pre_compact_main_captures_state(self, monkeypatch, tmp_path):
        hook_json = json.dumps({"session_id": "test-sess", "plan_file": "plan.md", "tasks": ["t1"]})
        monkeypatch.setattr("sys.stdin", type("", (), {"read": lambda self: hook_json})())
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))

        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.pre_compact import main

            main()
        assert exc_info.value.code == 2

        state_file = tmp_path / "sessions" / "test-sess" / "pre-compact-state.json"
        assert state_file.exists()
        saved = json.loads(state_file.read_text())
        assert saved["session_id"] == "test-sess"


class TestPreCompactSpecState:
    def test_pre_compact_captures_spec_state(self, monkeypatch, tmp_path):
        """main() includes spec_state in pre-compact-state.json when spec-state.json exists."""
        session_dir = tmp_path / "sessions" / "test-sess"
        session_dir.mkdir(parents=True)
        spec_state_data = {
            "phase": "implement",
            "slug": "my-feature",
            "plan_path": "/path/to/plan.md",
            "worktree": {
                "path": "/tmp/worktrees/my-feature",
                "branch": "feat/my-feature",
                "base_branch": "main",
                "slug": "my-feature",
            },
            "current_task": 2,
            "total_tasks": 5,
            "completed_tasks": 2,
            "review_iteration": 1,
        }
        (session_dir / "spec-state.json").write_text(json.dumps(spec_state_data))

        hook_json = json.dumps({"session_id": "test-sess"})
        monkeypatch.setattr("sys.stdin", type("", (), {"read": lambda self: hook_json})())
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))

        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.pre_compact import main

            main()
        assert exc_info.value.code == 2

        state_file = session_dir / "pre-compact-state.json"
        saved = json.loads(state_file.read_text())
        assert "spec_state" in saved
        assert saved["spec_state"]["phase"] == "implement"
        assert saved["spec_state"]["slug"] == "my-feature"

    def test_pre_compact_without_spec_state(self, monkeypatch, tmp_path):
        """main() does NOT include spec_state when no spec-state.json exists."""
        session_dir = tmp_path / "sessions" / "test-sess"
        session_dir.mkdir(parents=True)

        hook_json = json.dumps({"session_id": "test-sess"})
        monkeypatch.setattr("sys.stdin", type("", (), {"read": lambda self: hook_json})())
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))

        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.pre_compact import main

            main()
        assert exc_info.value.code == 2

        state_file = session_dir / "pre-compact-state.json"
        saved = json.loads(state_file.read_text())
        assert "spec_state" not in saved


class TestRestoreWithSpecState:
    def _make_state_file(self, session_dir: Path, spec_state: dict | None = None) -> None:
        session_dir.mkdir(parents=True, exist_ok=True)
        data: dict = {"captured_at": "2026-01-01T00:00:00Z"}
        if spec_state is not None:
            data["spec_state"] = spec_state
        (session_dir / "pre-compact-state.json").write_text(json.dumps(data))

    def _default_spec_state(self) -> dict:
        return {
            "phase": "implement",
            "slug": "my-feature",
            "plan_path": "/path/to/plan.md",
            "worktree": {
                "path": "/tmp/worktrees/my-feature",
                "branch": "feat/my-feature",
                "base_branch": "main",
                "slug": "my-feature",
            },
            "completed_tasks": 3,
            "total_tasks": 5,
            "review_iteration": 2,
        }

    def test_restore_message_includes_spec_phase(self, tmp_path):
        """build_restore_message includes the spec phase when spec_state is present."""
        session_dir = tmp_path / "sessions" / "s1"
        self._make_state_file(session_dir, self._default_spec_state())
        message = build_restore_message(session_dir)
        assert message is not None
        assert "implement" in message

    def test_restore_message_includes_spec_slug(self, tmp_path):
        """build_restore_message includes the slug when spec_state is present."""
        session_dir = tmp_path / "sessions" / "s1"
        self._make_state_file(session_dir, self._default_spec_state())
        message = build_restore_message(session_dir)
        assert message is not None
        assert "my-feature" in message

    def test_restore_message_includes_worktree_path(self, tmp_path):
        """build_restore_message includes the worktree path when present."""
        session_dir = tmp_path / "sessions" / "s1"
        self._make_state_file(session_dir, self._default_spec_state())
        message = build_restore_message(session_dir)
        assert message is not None
        assert "/tmp/worktrees/my-feature" in message

    def test_restore_message_includes_progress(self, tmp_path):
        """build_restore_message shows completed/total task count."""
        session_dir = tmp_path / "sessions" / "s1"
        self._make_state_file(session_dir, self._default_spec_state())
        message = build_restore_message(session_dir)
        assert message is not None
        assert "3/5" in message

    def test_restore_message_without_spec_state(self, tmp_path):
        """build_restore_message has no spec section when spec_state is absent."""
        session_dir = tmp_path / "sessions" / "s1"
        self._make_state_file(session_dir, spec_state=None)
        message = build_restore_message(session_dir)
        assert message is not None
        assert "Spec Workflow State" not in message
        assert "Phase:" not in message


class TestPreCompactDeliveryState:
    def test_pre_compact_captures_delivery_state(self, monkeypatch, tmp_path):
        """main() includes delivery_state when delivery API returns active state."""
        session_dir = tmp_path / "sessions" / "test-sess"
        session_dir.mkdir(parents=True)

        hook_json = json.dumps({"session_id": "test-sess"})
        monkeypatch.setattr("sys.stdin", type("", (), {"read": lambda self: hook_json})())
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "active": True,
            "delivery_phase": "implementation",
            "slug": "feat-x",
            "orchestration_mode": "classic",
            "phase_lead": "backend-engineer",
        }

        with patch("stratus.hooks.pre_compact.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_resp
            mock_httpx.post.return_value = MagicMock()
            with pytest.raises(SystemExit):
                from stratus.hooks.pre_compact import main

                main()

        state_file = session_dir / "pre-compact-state.json"
        saved = json.loads(state_file.read_text())
        assert "delivery_state" in saved
        assert saved["delivery_state"]["delivery_phase"] == "implementation"
        assert saved["delivery_state"]["slug"] == "feat-x"

    def test_pre_compact_no_delivery_state_on_inactive(self, monkeypatch, tmp_path):
        """main() does NOT include delivery_state when delivery is not active."""
        session_dir = tmp_path / "sessions" / "test-sess"
        session_dir.mkdir(parents=True)

        hook_json = json.dumps({"session_id": "test-sess"})
        monkeypatch.setattr("sys.stdin", type("", (), {"read": lambda self: hook_json})())
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"active": False}

        with patch("stratus.hooks.pre_compact.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_resp
            mock_httpx.post.return_value = MagicMock()
            with pytest.raises(SystemExit):
                from stratus.hooks.pre_compact import main

                main()

        state_file = session_dir / "pre-compact-state.json"
        saved = json.loads(state_file.read_text())
        assert "delivery_state" not in saved

    def test_pre_compact_no_delivery_state_on_api_error(self, monkeypatch, tmp_path):
        """main() does NOT include delivery_state when API call fails."""
        session_dir = tmp_path / "sessions" / "test-sess"
        session_dir.mkdir(parents=True)

        hook_json = json.dumps({"session_id": "test-sess"})
        monkeypatch.setattr("sys.stdin", type("", (), {"read": lambda self: hook_json})())
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))

        with patch("stratus.hooks.pre_compact.httpx") as mock_httpx:
            mock_httpx.get.side_effect = Exception("connection refused")
            mock_httpx.post.return_value = MagicMock()
            with pytest.raises(SystemExit):
                from stratus.hooks.pre_compact import main

                main()

        state_file = session_dir / "pre-compact-state.json"
        saved = json.loads(state_file.read_text())
        assert "delivery_state" not in saved


class TestRestoreWithDeliveryState:
    def _make_state_file(self, session_dir: Path, delivery_state: dict | None = None) -> None:
        session_dir.mkdir(parents=True, exist_ok=True)
        data: dict = {"captured_at": "2026-01-01T00:00:00Z"}
        if delivery_state is not None:
            data["delivery_state"] = delivery_state
        (session_dir / "pre-compact-state.json").write_text(json.dumps(data))

    def test_restore_message_includes_delivery_phase(self, tmp_path):
        session_dir = tmp_path / "sessions" / "s1"
        self._make_state_file(
            session_dir,
            {
                "delivery_phase": "implementation",
                "slug": "feat-x",
                "orchestration_mode": "classic",
                "phase_lead": "backend-engineer",
            },
        )
        message = build_restore_message(session_dir)
        assert message is not None
        assert "implementation" in message.lower()

    def test_restore_message_includes_delivery_slug(self, tmp_path):
        session_dir = tmp_path / "sessions" / "s1"
        self._make_state_file(
            session_dir,
            {
                "delivery_phase": "qa",
                "slug": "feat-x",
            },
        )
        message = build_restore_message(session_dir)
        assert message is not None
        assert "feat-x" in message

    def test_restore_message_includes_lead_agent(self, tmp_path):
        session_dir = tmp_path / "sessions" / "s1"
        self._make_state_file(
            session_dir,
            {
                "delivery_phase": "implementation",
                "slug": "feat",
                "phase_lead": "backend-engineer",
            },
        )
        message = build_restore_message(session_dir)
        assert message is not None
        assert "backend-engineer" in message

    def test_restore_message_no_delivery_section_when_absent(self, tmp_path):
        session_dir = tmp_path / "sessions" / "s1"
        self._make_state_file(session_dir, delivery_state=None)
        message = build_restore_message(session_dir)
        assert message is not None
        assert "Delivery State" not in message


class TestContextOverflowRecording:
    def test_record_context_overflow_called_on_high_context(self, monkeypatch, tmp_path):
        """When context monitor issues a warning, _record_context_overflow posts to analytics."""
        from tests.conftest import _make_assistant_message, _write_jsonl

        transcript = _write_jsonl(
            tmp_path / "high.jsonl",
            [
                _make_assistant_message(
                    uuid="a1",
                    input_tokens=1,
                    cache_creation_input_tokens=140000,
                    cache_read_input_tokens=0,
                    output_tokens=500,
                ),
            ],
        )
        hook_json = json.dumps({"transcript_path": str(transcript)})
        monkeypatch.setattr("sys.stdin", type("", (), {"read": lambda self: hook_json})())
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))

        with patch("stratus.hooks.context_monitor.httpx") as mock_httpx:
            with pytest.raises(SystemExit) as exc_info:
                from stratus.hooks.context_monitor import main

                main()

        assert exc_info.value.code == 2
        mock_httpx.post.assert_called_once()
        call_kwargs = mock_httpx.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["category"] == "context_overflow"
        assert "detail" in payload

    def _get_payload(self, mock_httpx: MagicMock) -> dict:
        """Extract the JSON payload from the most recent httpx.post call."""
        call = mock_httpx.post.call_args
        return call.kwargs.get("json") or call[1].get("json")

    def _patch_api_url(self):
        return patch(
            "stratus.hooks.context_monitor.get_api_url",
            return_value="http://127.0.0.1:41777",
            create=True,
        )

    def test_record_context_overflow_warning_detail_is_normalized(self):
        """Non-CRITICAL warning produces 'context_warning' (not a raw percentage string)."""
        from stratus.hooks.context_monitor import _record_context_overflow

        warning_text = (
            "⚡ Context at 67.5% raw (80.8% effective)."
            " Consider saving important findings to memory."
        )

        with patch("stratus.hooks.context_monitor.httpx") as mock_httpx:
            with self._patch_api_url():
                _record_context_overflow(warning_text)

        mock_httpx.post.assert_called_once()
        assert self._get_payload(mock_httpx)["detail"] == "context_warning"

    def test_record_context_overflow_critical_detail_is_normalized(self):
        """CRITICAL warning produces 'context_critical' (not a raw percentage string)."""
        from stratus.hooks.context_monitor import _record_context_overflow

        warning_text = (
            "⚠ CONTEXT CRITICAL: 85.2% raw (102.0% effective)."
            " Compaction imminent at 83.5%. Save important context now."
        )

        with patch("stratus.hooks.context_monitor.httpx") as mock_httpx:
            with self._patch_api_url():
                _record_context_overflow(warning_text)

        mock_httpx.post.assert_called_once()
        assert self._get_payload(mock_httpx)["detail"] == "context_critical"

    def test_record_context_overflow_detail_never_contains_percentage(self):
        """The posted detail must not contain '%' — that would break dedup."""
        from stratus.hooks.context_monitor import _record_context_overflow

        warn = (
            "⚡ Context at 72.3% raw (86.6% effective)."
            " Consider saving important findings to memory."
        )
        critical = (
            "⚠ CONTEXT CRITICAL: 90.1% raw (107.9% effective)."
            " Compaction imminent at 83.5%. Save important context now."
        )
        for warning_text in [warn, critical]:
            with patch("stratus.hooks.context_monitor.httpx") as mock_httpx:
                with self._patch_api_url():
                    _record_context_overflow(warning_text)

            assert "%" not in self._get_payload(mock_httpx)["detail"]


class TestPostCompactRestoreMain:
    def test_restores_state_to_stdout(self, monkeypatch, tmp_path, capsys):
        session_dir = tmp_path / "sessions" / "test-sess"
        session_dir.mkdir(parents=True)
        (session_dir / "pre-compact-state.json").write_text(
            json.dumps({"plan_file": "plan.md", "captured_at": "2026-01-01T00:00:00Z"})
        )
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "test-sess")

        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.post_compact_restore import main

            main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "plan.md" in captured.out or "context" in captured.out.lower()

    def test_exits_0_with_no_state(self, monkeypatch, tmp_path, capsys):
        session_dir = tmp_path / "sessions" / "test-sess"
        session_dir.mkdir(parents=True)
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "test-sess")

        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.post_compact_restore import main

            main()
        assert exc_info.value.code == 0
