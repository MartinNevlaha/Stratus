"""Tests for statusline output formatting."""

from __future__ import annotations

import json
from unittest.mock import patch

from stratus.statusline import format_context_section, format_statusline, format_stratus_section


class TestFormatStratusSection:
    def test_inactive_when_no_workflow(self) -> None:
        state = {
            "orchestration": {"mode": "inactive", "spec": None},
        }
        result = format_stratus_section(state)
        assert result == "inactive"

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
        result = format_stratus_section(state)
        assert "plan" in result
        assert "my-feat" in result
        assert "2/5" in result

    def test_server_offline_returns_offline(self) -> None:
        result = format_stratus_section(None)
        assert result == "offline"


class TestFormatContextSection:
    def test_correct_token_math_and_percentage(self) -> None:
        stdin_data = {
            "context_window": {
                "context_window_size": 200000,
                "current_usage": {
                    "input_tokens": 5000,
                    "cache_read_input_tokens": 7000,
                    "cache_creation_input_tokens": 500,
                },
            },
        }
        result = format_context_section(stdin_data)
        # Total = 5000 + 7000 + 500 = 12500 tokens = 12.5k
        assert "12.5k" in result
        assert "200k" in result
        assert "6.2%" in result

    def test_zero_usage(self) -> None:
        stdin_data = {
            "context_window": {
                "context_window_size": 200000,
                "current_usage": {
                    "input_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                },
            },
        }
        result = format_context_section(stdin_data)
        assert "0.0k" in result
        assert "0.0%" in result

    def test_missing_context_window_data(self) -> None:
        result = format_context_section({})
        assert "ctx" in result


class TestFormatStatusline:
    def test_full_output_contains_all_segments(self) -> None:
        stdin_data = {
            "model": {"display_name": "Opus"},
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
        stratus_state = {
            "orchestration": {"mode": "inactive", "spec": None},
        }
        result = format_statusline(stdin_data, stratus_state)
        assert "Opus" in result
        assert "ctx:" in result
        assert "stratus:" in result
        assert "|" in result

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
        result = format_statusline(stdin_data, None)
        assert "offline" in result
        assert "Sonnet" in result


class TestRunStatusline:
    def test_run_reads_stdin_and_outputs(self) -> None:
        stdin_data = {
            "model": {"display_name": "Opus"},
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
        state_response = {
            "orchestration": {"mode": "inactive", "spec": None},
        }
        with (
            patch("sys.stdin") as mock_stdin,
            patch("stratus.statusline.fetch_stratus_state", return_value=state_response),
            patch("builtins.print") as mock_print,
        ):
            mock_stdin.read.return_value = json.dumps(stdin_data)
            from stratus.statusline import run

            run()
        mock_print.assert_called_once()
        output = mock_print.call_args[0][0]
        assert "Opus" in output
        assert "stratus:" in output
