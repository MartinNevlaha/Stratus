"""Tests for the file_checker PostToolUse hook."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from stratus.hooks.file_checker import detect_language, run_linters


class TestDetectLanguage:
    def test_detect_language_python(self):
        assert detect_language("script.py") == "python"

    def test_detect_language_typescript(self):
        assert detect_language("component.ts") == "typescript"

    def test_detect_language_tsx(self):
        assert detect_language("App.tsx") == "typescript"

    def test_detect_language_javascript(self):
        assert detect_language("index.js") == "typescript"

    def test_detect_language_jsx(self):
        assert detect_language("Button.jsx") == "typescript"

    def test_detect_language_go(self):
        assert detect_language("main.go") == "go"

    def test_detect_language_unknown(self):
        assert detect_language("README.txt") is None

    def test_detect_language_no_extension(self):
        assert detect_language("Makefile") is None

    def test_detect_language_absolute_path_python(self):
        assert detect_language("/home/user/project/foo.py") == "python"


class TestRunLintersPython:
    def test_run_linters_python_success(self):
        """All linters pass → empty error list."""
        ok = MagicMock()
        ok.returncode = 0
        ok.stdout = ""
        ok.stderr = ""
        with patch("subprocess.run", return_value=ok) as mock_run:
            errors = run_linters("script.py", "python")
        assert errors == []
        assert mock_run.call_count >= 2  # ruff check + ruff format at minimum

    def test_run_linters_python_failure(self):
        """Linter exits with returncode 1 → errors reported."""
        fail = MagicMock()
        fail.returncode = 1
        fail.stdout = "E501 line too long"
        fail.stderr = ""

        ok = MagicMock()
        ok.returncode = 0
        ok.stdout = ""
        ok.stderr = ""

        # Python has 3 linter commands: ruff check, ruff format, basedpyright
        # First call (ruff check) fails, rest pass
        with patch("subprocess.run", side_effect=[fail, ok, ok]):
            errors = run_linters("script.py", "python")
        assert len(errors) > 0
        assert any("E501" in e or "ruff" in e.lower() for e in errors)

    def test_run_linters_skips_missing_tool(self):
        """FileNotFoundError → skip silently, no errors."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            errors = run_linters("script.py", "python")
        assert errors == []


class TestRunLintersGo:
    def test_run_linters_go_success(self):
        ok = MagicMock()
        ok.returncode = 0
        ok.stdout = ""
        ok.stderr = ""
        with patch("subprocess.run", return_value=ok):
            errors = run_linters("main.go", "go")
        assert errors == []

    def test_run_linters_go_failure(self):
        fail = MagicMock()
        fail.returncode = 1
        fail.stdout = "golangci-lint: issue found"
        fail.stderr = ""

        ok = MagicMock()
        ok.returncode = 0
        ok.stdout = ""
        ok.stderr = ""

        with patch("subprocess.run", side_effect=[ok, fail]):
            errors = run_linters("main.go", "go")
        assert len(errors) > 0


class TestRunLintersTypeScript:
    def test_run_linters_typescript_success(self):
        ok = MagicMock()
        ok.returncode = 0
        ok.stdout = ""
        ok.stderr = ""
        with patch("subprocess.run", return_value=ok):
            errors = run_linters("app.ts", "typescript")
        assert errors == []


class TestMain:
    def _make_stdin(self, data: dict) -> object:
        return type("FakeStdin", (), {"read": lambda self: json.dumps(data)})()

    def test_main_ignores_non_write_tool(self, monkeypatch):
        """tool_name=Read → exit 0 without running linters."""
        hook_data = {"tool_name": "Read", "tool_input": {"file_path": "foo.py"}}
        monkeypatch.setattr("sys.stdin", self._make_stdin(hook_data))
        with patch("stratus.hooks.file_checker.run_linters") as mock_linters:
            with pytest.raises(SystemExit) as exc_info:
                from stratus.hooks.file_checker import main
                main()
        assert exc_info.value.code == 0
        mock_linters.assert_not_called()

    def test_main_ignores_bash_tool(self, monkeypatch):
        hook_data = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
        monkeypatch.setattr("sys.stdin", self._make_stdin(hook_data))
        with patch("stratus.hooks.file_checker.run_linters") as mock_linters:
            with pytest.raises(SystemExit) as exc_info:
                from stratus.hooks.file_checker import main
                main()
        assert exc_info.value.code == 0
        mock_linters.assert_not_called()

    def test_main_runs_linters_on_write(self, monkeypatch):
        """tool_name=Write with foo.py → calls run_linters."""
        hook_data = {"tool_name": "Write", "tool_input": {"file_path": "foo.py"}}
        monkeypatch.setattr("sys.stdin", self._make_stdin(hook_data))
        with patch(
            "stratus.hooks.file_checker.run_linters", return_value=[]
        ) as mock_linters:
            with pytest.raises(SystemExit) as exc_info:
                from stratus.hooks.file_checker import main
                main()
        assert exc_info.value.code == 0
        mock_linters.assert_called_once_with("foo.py", "python")

    def test_main_runs_linters_on_edit(self, monkeypatch):
        """tool_name=Edit → calls run_linters."""
        hook_data = {"tool_name": "Edit", "tool_input": {"file_path": "app.ts"}}
        monkeypatch.setattr("sys.stdin", self._make_stdin(hook_data))
        with patch(
            "stratus.hooks.file_checker.run_linters", return_value=[]
        ) as mock_linters:
            with pytest.raises(SystemExit) as exc_info:
                from stratus.hooks.file_checker import main
                main()
        assert exc_info.value.code == 0
        mock_linters.assert_called_once_with("app.ts", "typescript")

    def test_main_exits_0_on_unknown_extension(self, monkeypatch):
        """Unknown file extension → exit 0 silently, no linters."""
        hook_data = {"tool_name": "Write", "tool_input": {"file_path": "notes.txt"}}
        monkeypatch.setattr("sys.stdin", self._make_stdin(hook_data))
        with patch("stratus.hooks.file_checker.run_linters") as mock_linters:
            with pytest.raises(SystemExit) as exc_info:
                from stratus.hooks.file_checker import main
                main()
        assert exc_info.value.code == 0
        mock_linters.assert_not_called()

    def test_main_exits_2_on_linter_errors(self, monkeypatch, capsys):
        """Linter returns errors → exit 2 and print to stderr."""
        hook_data = {"tool_name": "Write", "tool_input": {"file_path": "script.py"}}
        monkeypatch.setattr("sys.stdin", self._make_stdin(hook_data))
        with patch(
            "stratus.hooks.file_checker.run_linters",
            return_value=["E501 line too long"],
        ):
            with pytest.raises(SystemExit) as exc_info:
                from stratus.hooks.file_checker import main
                main()
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "E501" in captured.err

    def test_main_exits_0_on_empty_stdin(self, monkeypatch):
        """Empty stdin → exit 0 gracefully."""
        monkeypatch.setattr(
            "sys.stdin", type("FakeStdin", (), {"read": lambda self: ""})()
        )
        with pytest.raises(SystemExit) as exc_info:
            from stratus.hooks.file_checker import main
            main()
        assert exc_info.value.code == 0

    def test_main_records_lint_failures_on_exit_2(self, monkeypatch):
        """On linter errors, _record_lint_failures is called with joined errors before exit 2."""
        hook_data = {"tool_name": "Write", "tool_input": {"file_path": "script.py"}}
        monkeypatch.setattr("sys.stdin", self._make_stdin(hook_data))
        errors = ["ruff: E501 line too long", "basedpyright: type error found"]
        with patch("stratus.hooks.file_checker.run_linters", return_value=errors):
            with patch("stratus.hooks.file_checker.httpx") as mock_httpx:
                with pytest.raises(SystemExit) as exc_info:
                    from stratus.hooks.file_checker import main
                    main()
        assert exc_info.value.code == 2
        mock_httpx.post.assert_called_once()
        call_kwargs = mock_httpx.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["category"] == "lint_error"
        assert payload["file_path"] == "script.py"
        # Both errors joined into one detail string
        assert "E501" in payload["detail"]
        assert "type error" in payload["detail"]
