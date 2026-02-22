"""Tests for the agent_tracker hook."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestHandlePreToolUse:
    def test_calls_api_with_subagent_type_implement(self):
        from stratus.hooks.agent_tracker import handle_pre_tool_use

        with patch("stratus.hooks.agent_tracker._call_api") as mock_api:
            handle_pre_tool_use({"subagent_type": "mobile-dev-specialist"}, "implement")
            mock_api.assert_called_once_with("mobile-dev-specialist")

    def test_calls_api_with_subagent_type_verify(self):
        from stratus.hooks.agent_tracker import handle_pre_tool_use

        with patch("stratus.hooks.agent_tracker._call_api") as mock_api:
            handle_pre_tool_use({"subagent_type": "spec-reviewer-compliance"}, "verify")
            mock_api.assert_called_once_with("spec-reviewer-compliance")

    def test_calls_api_with_subagent_type_plan(self):
        from stratus.hooks.agent_tracker import handle_pre_tool_use

        with patch("stratus.hooks.agent_tracker._call_api") as mock_api:
            handle_pre_tool_use({"subagent_type": "architecture-guide"}, "plan")
            mock_api.assert_called_once_with("architecture-guide")

    def test_calls_api_with_subagent_type_learn(self):
        from stratus.hooks.agent_tracker import handle_pre_tool_use

        with patch("stratus.hooks.agent_tracker._call_api") as mock_api:
            handle_pre_tool_use({"subagent_type": "learning-agent"}, "learn")
            mock_api.assert_called_once_with("learning-agent")

    def test_skips_no_phase(self):
        from stratus.hooks.agent_tracker import handle_pre_tool_use

        with patch("stratus.hooks.agent_tracker._call_api") as mock_api:
            handle_pre_tool_use({"subagent_type": "some-agent"}, None)
            mock_api.assert_not_called()

    def test_skips_missing_subagent_type(self):
        from stratus.hooks.agent_tracker import handle_pre_tool_use

        with patch("stratus.hooks.agent_tracker._call_api") as mock_api:
            handle_pre_tool_use({}, "implement")
            mock_api.assert_not_called()

    def test_skips_empty_subagent_type(self):
        from stratus.hooks.agent_tracker import handle_pre_tool_use

        with patch("stratus.hooks.agent_tracker._call_api") as mock_api:
            handle_pre_tool_use({"subagent_type": ""}, "implement")
            mock_api.assert_not_called()


class TestHandlePostToolUse:
    def test_clears_agent_id_implement(self):
        from stratus.hooks.agent_tracker import handle_post_tool_use

        with patch("stratus.hooks.agent_tracker._call_api") as mock_api:
            handle_post_tool_use("implement")
            mock_api.assert_called_once_with(None)

    def test_clears_agent_id_verify(self):
        from stratus.hooks.agent_tracker import handle_post_tool_use

        with patch("stratus.hooks.agent_tracker._call_api") as mock_api:
            handle_post_tool_use("verify")
            mock_api.assert_called_once_with(None)

    def test_clears_agent_id_plan(self):
        from stratus.hooks.agent_tracker import handle_post_tool_use

        with patch("stratus.hooks.agent_tracker._call_api") as mock_api:
            handle_post_tool_use("plan")
            mock_api.assert_called_once_with(None)

    def test_clears_agent_id_learn(self):
        from stratus.hooks.agent_tracker import handle_post_tool_use

        with patch("stratus.hooks.agent_tracker._call_api") as mock_api:
            handle_post_tool_use("learn")
            mock_api.assert_called_once_with(None)

    def test_skips_no_phase(self):
        from stratus.hooks.agent_tracker import handle_post_tool_use

        with patch("stratus.hooks.agent_tracker._call_api") as mock_api:
            handle_post_tool_use(None)
            mock_api.assert_not_called()


class TestCallApi:
    def test_returns_true_on_success(self):
        from stratus.hooks.agent_tracker import _call_api

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response
            result = _call_api("test-agent")
            assert result is True

    def test_returns_false_on_error(self):
        from stratus.hooks.agent_tracker import _call_api

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.side_effect = Exception(
                "Connection failed"
            )
            result = _call_api("test-agent")
            assert result is False

    def test_returns_false_on_non_200(self):
        from stratus.hooks.agent_tracker import _call_api

        mock_response = MagicMock()
        mock_response.status_code = 409

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response
            result = _call_api("test-agent")
            assert result is False


class TestMain:
    def test_exits_0_on_pre_tool_use_task(self, capsys):
        from stratus.hooks.agent_tracker import main

        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Task",
            "tool_input": {"subagent_type": "test-agent"},
        }

        with (
            patch("stratus.hooks._common.read_hook_input", return_value=payload),
            patch("stratus.hooks.agent_tracker._get_active_phase", return_value="implement"),
            patch("stratus.hooks.agent_tracker._call_api", return_value=True),
        ):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0

    def test_exits_0_on_post_tool_use_task(self, capsys):
        from stratus.hooks.agent_tracker import main

        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Task",
            "tool_input": {"subagent_type": "test-agent"},
        }

        with (
            patch("stratus.hooks._common.read_hook_input", return_value=payload),
            patch("stratus.hooks.agent_tracker._get_active_phase", return_value="implement"),
            patch("stratus.hooks.agent_tracker._call_api", return_value=True),
        ):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0

    def test_exits_0_on_non_task_tool(self):
        from stratus.hooks.agent_tracker import main

        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "/some/file.py"},
        }

        with patch("stratus.hooks._common.read_hook_input", return_value=payload):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0

    def test_exits_0_on_exception(self):
        from stratus.hooks.agent_tracker import main

        with patch(
            "stratus.hooks._common.read_hook_input",
            side_effect=Exception("Boom"),
        ):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0
