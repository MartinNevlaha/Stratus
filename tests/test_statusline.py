"""Tests for statusline output formatting."""

from __future__ import annotations

import json
import re
from unittest.mock import patch

from stratus.statusline import (
    _format_duration,
    format_context_segment,
    format_cost_segment,
    format_git_segment,
    format_model_segment,
    format_session_segment,
    format_statusline,
    format_stratus_segment,
)


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestFormatGitSegment:
    def test_returns_branch_with_icon(self) -> None:
        with patch("stratus.statusline._get_git_branch", return_value="main"):
            result = format_git_segment("/tmp")
        assert result is not None
        stripped = _strip_ansi(result)
        assert "⎇" in stripped
        assert "main" in stripped

    def test_returns_none_when_no_branch(self) -> None:
        with patch("stratus.statusline._get_git_branch", return_value=""):
            result = format_git_segment("/tmp")
        assert result is None

    def test_has_magenta_color(self) -> None:
        with patch("stratus.statusline._get_git_branch", return_value="feat"):
            result = format_git_segment("/tmp")
        assert result is not None
        assert "\x1b[35m" in result


class TestFormatModelSegment:
    def test_returns_model_name(self) -> None:
        data = {"model": {"display_name": "Opus"}}
        result = format_model_segment(data)
        assert result is not None
        assert "Opus" in _strip_ansi(result)

    def test_falls_back_to_id(self) -> None:
        data = {"model": {"id": "claude-opus-4-20250514"}}
        result = format_model_segment(data)
        assert result is not None
        assert "claude-opus-4-20250514" in _strip_ansi(result)

    def test_handles_string_model(self) -> None:
        data = {"model": "Sonnet"}
        result = format_model_segment(data)
        assert result is not None
        assert "Sonnet" in _strip_ansi(result)

    def test_returns_none_when_missing(self) -> None:
        assert format_model_segment({}) is None

    def test_has_cyan_color(self) -> None:
        data = {"model": {"display_name": "Opus"}}
        result = format_model_segment(data)
        assert result is not None
        assert "\x1b[36m" in result


class TestFormatCostSegment:
    def test_formats_cost(self) -> None:
        data = {"cost": {"total_cost_usd": 2.5}}
        result = format_cost_segment(data)
        assert result is not None
        assert "$2.50" in _strip_ansi(result)

    def test_returns_none_when_missing(self) -> None:
        assert format_cost_segment({}) is None
        assert format_cost_segment({"cost": {}}) is None

    def test_has_green_color(self) -> None:
        data = {"cost": {"total_cost_usd": 1.0}}
        result = format_cost_segment(data)
        assert result is not None
        assert "\x1b[32m" in result


class TestFormatSessionSegment:
    def test_formats_hours_and_minutes(self) -> None:
        data = {"cost": {"total_duration_ms": 5580000}}  # 1hr 33m
        result = format_session_segment(data)
        assert result is not None
        assert "1hr 33m" in _strip_ansi(result)

    def test_formats_minutes_only(self) -> None:
        data = {"cost": {"total_duration_ms": 300000}}  # 5m
        result = format_session_segment(data)
        assert result is not None
        stripped = _strip_ansi(result)
        assert "5m" in stripped
        assert "hr" not in stripped

    def test_returns_none_when_missing(self) -> None:
        assert format_session_segment({}) is None

    def test_has_yellow_color(self) -> None:
        data = {"cost": {"total_duration_ms": 60000}}
        result = format_session_segment(data)
        assert result is not None
        assert "\x1b[33m" in result


class TestFormatDuration:
    def test_hours_and_minutes(self) -> None:
        assert _format_duration(7380000) == "2hr 3m"

    def test_minutes_only(self) -> None:
        assert _format_duration(720000) == "12m"

    def test_zero(self) -> None:
        assert _format_duration(0) == "0m"


class TestFormatContextSegment:
    def test_correct_percentage(self) -> None:
        data = {
            "context_window": {
                "context_window_size": 200000,
                "current_usage": {
                    "input_tokens": 5000,
                    "cache_read_input_tokens": 7000,
                    "cache_creation_input_tokens": 500,
                },
            },
        }
        result = format_context_segment(data)
        assert result is not None
        stripped = _strip_ansi(result)
        assert "Ctx:" in stripped
        assert "6.2%" in stripped

    def test_zero_usage(self) -> None:
        data = {
            "context_window": {
                "context_window_size": 200000,
                "current_usage": {
                    "input_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                },
            },
        }
        result = format_context_segment(data)
        assert result is not None
        assert "0.0%" in _strip_ansi(result)

    def test_returns_none_without_window_size(self) -> None:
        assert format_context_segment({}) is None

    def test_has_blue_color(self) -> None:
        data = {
            "context_window": {
                "context_window_size": 200000,
                "current_usage": {
                    "input_tokens": 1000,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                },
            },
        }
        result = format_context_segment(data)
        assert result is not None
        assert "\x1b[34m" in result


class TestFormatStratusSegment:
    def test_idle_when_inactive(self) -> None:
        state = {"orchestration": {"mode": "inactive", "spec": None}}
        result = format_stratus_segment(state)
        stripped = _strip_ansi(result)
        assert "idle" in stripped
        assert "◈" in stripped
        assert "\x1b[32m" in result  # GREEN icon when online

    def test_shows_spec_phase_and_slug(self) -> None:
        state = {
            "orchestration": {
                "mode": "spec",
                "spec": {
                    "phase": "plan",
                    "slug": "my-feat",
                    "completed_tasks": 2,
                    "total_tasks": 5,
                },
            },
        }
        result = format_stratus_segment(state)
        stripped = _strip_ansi(result)
        assert "◈" in stripped
        assert "plan" in stripped
        assert "my-feat" in stripped
        assert "2/5" in stripped

    def test_shows_delivery_phase(self) -> None:
        state = {
            "orchestration": {
                "mode": "delivery",
                "delivery": {"delivery_phase": "implement", "slug": "auth"},
            },
        }
        result = format_stratus_segment(state)
        stripped = _strip_ansi(result)
        assert "◈" in stripped
        assert "implement" in stripped
        assert "auth" in stripped

    def test_offline_when_none(self) -> None:
        result = format_stratus_segment(None)
        stripped = _strip_ansi(result)
        assert "◈" in stripped
        assert "offline" in stripped
        assert "\x1b[31m" in result  # RED icon when offline

    def test_has_red_color_when_offline(self) -> None:
        result = format_stratus_segment(None)
        assert "\x1b[31m" in result  # RED for offline avatar icon

    def test_shows_version_when_idle(self) -> None:
        state = {
            "orchestration": {"mode": "inactive", "spec": None},
            "version": "0.8.0",
        }
        result = format_stratus_segment(state)
        stripped = _strip_ansi(result)
        assert "v0.8.0" in stripped

    def test_shows_agent_count(self) -> None:
        state = {
            "orchestration": {
                "mode": "spec",
                "spec": {
                    "phase": "implement",
                    "slug": "feat",
                    "completed_tasks": 1,
                    "total_tasks": 3,
                },
            },
            "agents": [
                {"id": "a1", "active": True},
                {"id": "a2", "active": True},
            ],
        }
        result = format_stratus_segment(state)
        stripped = _strip_ansi(result)
        assert "[2 agents]" in stripped

    def test_no_agent_count_when_none_active(self) -> None:
        state = {
            "orchestration": {
                "mode": "spec",
                "spec": {
                    "phase": "implement",
                    "slug": "feat",
                    "completed_tasks": 1,
                    "total_tasks": 3,
                },
            },
            "agents": [],
        }
        result = format_stratus_segment(state)
        stripped = _strip_ansi(result)
        assert "[" not in stripped

    def test_green_icon_when_online(self) -> None:
        state = {"orchestration": {"mode": "inactive", "spec": None}}
        result = format_stratus_segment(state)
        assert "\x1b[32m" in result  # GREEN for online avatar icon


class TestFormatStatusline:
    def test_full_output_contains_all_segments(self) -> None:
        stdin_data = {
            "model": {"display_name": "Opus"},
            "cost": {"total_cost_usd": 1.23, "total_duration_ms": 3600000},
            "context_window": {
                "context_window_size": 200000,
                "current_usage": {
                    "input_tokens": 5000,
                    "cache_read_input_tokens": 7000,
                    "cache_creation_input_tokens": 500,
                },
            },
            "workspace": {"current_dir": "/home/user/project"},
        }
        stratus_state = {"orchestration": {"mode": "inactive", "spec": None}}
        with patch("stratus.statusline._get_git_branch", return_value="main"):
            result = format_statusline(stdin_data, stratus_state)
        stripped = _strip_ansi(result)
        assert "main" in stripped
        assert "Opus" in stripped
        assert "$1.23" in stripped
        assert "1hr" in stripped
        assert "Ctx:" in stripped
        assert "◈" in stripped

    def test_uses_nbsp(self) -> None:
        stdin_data = {
            "model": {"display_name": "Opus"},
            "context_window": {
                "context_window_size": 200000,
                "current_usage": {
                    "input_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                },
            },
            "workspace": {"current_dir": "/tmp"},
        }
        with patch("stratus.statusline._get_git_branch", return_value=""):
            result = format_statusline(stdin_data, None)
        # Should not contain regular spaces (all replaced with NBSP)
        # Strip the ANSI codes first, then check
        # Note: ANSI codes themselves don't contain spaces
        text_only = _strip_ansi(result)
        assert " " not in text_only  # no regular spaces
        assert "\u00a0" in text_only  # has non-breaking spaces

    def test_starts_with_ansi_reset(self) -> None:
        stdin_data = {"model": {"display_name": "X"}, "workspace": {}}
        with patch("stratus.statusline._get_git_branch", return_value=""):
            result = format_statusline(stdin_data, None)
        assert result.startswith("\x1b[0m")

    def test_output_with_server_offline(self) -> None:
        stdin_data = {
            "model": {"display_name": "Sonnet"},
            "context_window": {
                "context_window_size": 200000,
                "current_usage": {
                    "input_tokens": 1000,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                },
            },
            "workspace": {"current_dir": "/tmp"},
        }
        with patch("stratus.statusline._get_git_branch", return_value="dev"):
            result = format_statusline(stdin_data, None)
        stripped = _strip_ansi(result)
        assert "offline" in stripped
        assert "◈" in stripped
        assert "Sonnet" in stripped

    def test_omits_segments_without_data(self) -> None:
        """Segments with no data are omitted, not shown as empty."""
        stdin_data = {"workspace": {}}
        with patch("stratus.statusline._get_git_branch", return_value=""):
            result = format_statusline(stdin_data, None)
        stripped = _strip_ansi(result)
        # Only stratus segment should remain (always present)
        assert "◈" in stripped
        # Should not have multiple separators stacked
        assert "||" not in stripped


class TestRunStatusline:
    def test_run_reads_stdin_and_outputs(self) -> None:
        stdin_data = {
            "model": {"display_name": "Opus"},
            "cost": {"total_cost_usd": 0.50, "total_duration_ms": 120000},
            "context_window": {
                "context_window_size": 200000,
                "current_usage": {
                    "input_tokens": 5000,
                    "cache_read_input_tokens": 7000,
                    "cache_creation_input_tokens": 500,
                },
            },
            "workspace": {"current_dir": "/tmp/project"},
        }
        state_response = {"orchestration": {"mode": "inactive", "spec": None}}
        with (
            patch("sys.stdin") as mock_stdin,
            patch("stratus.statusline.fetch_stratus_state", return_value=state_response),
            patch("builtins.print") as mock_print,
            patch("stratus.statusline._get_git_branch", return_value="main"),
        ):
            mock_stdin.read.return_value = json.dumps(stdin_data)
            from stratus.statusline import run

            run()
        mock_print.assert_called_once()
        output = mock_print.call_args[0][0]
        stripped = _strip_ansi(output)
        assert "Opus" in stripped
        assert "◈" in stripped
