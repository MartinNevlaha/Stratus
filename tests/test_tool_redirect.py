"""Tests for PreToolUse hook: tool_redirect."""

import json

import pytest

from stratus.hooks.tool_redirect import (
    build_redirect_message,
    classify_query,
)


class TestClassifyQuery:
    def test_classify_query_code_search(self):
        result = classify_query("where is the retry pattern implemented")
        assert result == "code"

    def test_classify_query_rule_search(self):
        result = classify_query("what are the naming conventions")
        assert result == "rule"

    def test_classify_query_library(self):
        result = classify_query("starlette middleware documentation")
        assert result == "library"

    def test_classify_query_general(self):
        result = classify_query("python 3.12 release notes")
        assert result == "general"

    def test_classify_query_implementation_keyword(self):
        result = classify_query("show me the implementation of the parser")
        assert result == "code"

    def test_classify_query_function_keyword(self):
        result = classify_query("what does the function do")
        assert result == "code"

    def test_classify_query_policy_keyword(self):
        result = classify_query("what is the policy for error handling")
        assert result == "rule"

    def test_classify_query_pydantic_library(self):
        result = classify_query("pydantic v2 validators")
        assert result == "library"

    def test_classify_query_httpx_library(self):
        result = classify_query("httpx async client usage")
        assert result == "library"

    def test_classify_query_mcp_library(self):
        result = classify_query("mcp protocol tool registration")
        assert result == "library"

    def test_classify_query_case_insensitive(self):
        result = classify_query("WHERE IS the Class defined")
        assert result == "code"


class TestBuildRedirectMessage:
    def test_build_redirect_message_code(self):
        msg = build_redirect_message("code", "where is retry implemented")
        assert msg is not None
        assert len(msg) > 0

    def test_build_redirect_message_rule(self):
        msg = build_redirect_message("rule", "naming conventions")
        assert msg is not None
        assert len(msg) > 0

    def test_build_redirect_message_library(self):
        msg = build_redirect_message("library", "starlette docs")
        assert msg is None

    def test_build_redirect_message_general(self):
        msg = build_redirect_message("general", "python 3.12 release notes")
        assert msg is None

    def test_build_redirect_message_code_mentions_retrieve(self):
        msg = build_redirect_message("code", "where is X")
        assert msg is not None
        assert "retrieve" in msg.lower()

    def test_build_redirect_message_rule_mentions_retrieve(self):
        msg = build_redirect_message("rule", "conventions")
        assert msg is not None
        assert "retrieve" in msg.lower()


class TestMain:
    def _make_stdin(self, data: dict):
        """Return a mock stdin object that yields the given dict as JSON."""
        return type("FakeStdin", (), {"read": lambda self: json.dumps(data)})()

    def test_main_ignores_non_web_tools(self, monkeypatch):
        hook_json = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
        monkeypatch.setattr("sys.stdin", self._make_stdin(hook_json))
        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.tool_redirect import main

            main()
        assert exc_info.value.code == 0

    def test_main_redirects_code_search(self, monkeypatch, capsys):
        hook_json = {
            "tool_name": "WebSearch",
            "tool_input": {"query": "where is the retry logic implemented"},
        }
        monkeypatch.setattr("sys.stdin", self._make_stdin(hook_json))
        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.tool_redirect import main

            main()
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert captured.err  # some message was printed to stderr

    def test_main_allows_general_search(self, monkeypatch):
        hook_json = {
            "tool_name": "WebSearch",
            "tool_input": {"query": "python docs"},
        }
        monkeypatch.setattr("sys.stdin", self._make_stdin(hook_json))
        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.tool_redirect import main

            main()
        assert exc_info.value.code == 0

    def test_main_redirects_rule_search_via_webfetch(self, monkeypatch, capsys):
        hook_json = {
            "tool_name": "WebFetch",
            "tool_input": {"url": "https://example.com/coding-standards-and-conventions"},
        }
        monkeypatch.setattr("sys.stdin", self._make_stdin(hook_json))
        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.tool_redirect import main

            main()
        assert exc_info.value.code == 2

    def test_main_allows_library_search(self, monkeypatch):
        hook_json = {
            "tool_name": "WebSearch",
            "tool_input": {"query": "starlette routing documentation"},
        }
        monkeypatch.setattr("sys.stdin", self._make_stdin(hook_json))
        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.tool_redirect import main

            main()
        assert exc_info.value.code == 0

    def test_main_exits_0_on_empty_input(self, monkeypatch):
        monkeypatch.setattr(
            "sys.stdin", type("FakeStdin", (), {"read": lambda self: ""})()
        )
        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.tool_redirect import main

            main()
        assert exc_info.value.code == 0

    def test_main_webfetch_allows_library_url(self, monkeypatch):
        hook_json = {
            "tool_name": "WebFetch",
            "tool_input": {"url": "https://docs.pydantic.dev/latest/"},
        }
        monkeypatch.setattr("sys.stdin", self._make_stdin(hook_json))
        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.tool_redirect import main

            main()
        assert exc_info.value.code == 0
