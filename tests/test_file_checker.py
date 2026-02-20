"""Tests for the file_checker PostToolUse hook."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from stratus.hooks.file_checker import _find_config_up, detect_language, run_linters


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


class TestFindConfigUp:
    def test_finds_config_in_same_directory(self, tmp_path):
        """Config file in the file's own directory is found."""
        ts_file = tmp_path / "app.ts"
        ts_file.touch()
        (tmp_path / ".eslintrc.json").touch()
        assert _find_config_up(str(ts_file), [".eslintrc.json"]) is True

    def test_finds_config_in_parent_directory(self, tmp_path):
        """Config file in a parent directory is found."""
        sub = tmp_path / "src"
        sub.mkdir()
        ts_file = sub / "app.ts"
        ts_file.touch()
        (tmp_path / ".eslintrc.json").touch()
        assert _find_config_up(str(ts_file), [".eslintrc.json"]) is True

    def test_returns_false_when_no_config_exists(self, tmp_path):
        """No config file anywhere up the tree → returns False."""
        # Use a .git dir to bound the search so it doesn't escape tmp_path
        (tmp_path / ".git").mkdir()
        sub = tmp_path / "src"
        sub.mkdir()
        ts_file = sub / "app.ts"
        ts_file.touch()
        assert _find_config_up(str(ts_file), [".eslintrc.json"]) is False

    def test_stops_at_git_directory(self, tmp_path):
        """Search stops at a .git directory and does not go above it."""
        (tmp_path / ".git").mkdir()
        sub = tmp_path / "sub"
        sub.mkdir()
        ts_file = sub / "app.ts"
        ts_file.touch()
        # Place config above the .git boundary — must NOT be found
        parent = tmp_path.parent
        config = parent / ".eslintrc.json"
        config_existed = config.exists()
        if not config_existed:
            config.touch()
        try:
            result = _find_config_up(str(ts_file), [".eslintrc.json"])
        finally:
            if not config_existed:
                config.unlink(missing_ok=True)
        # Should not find the config above the .git boundary
        assert result is False

    def test_matches_any_of_multiple_config_names(self, tmp_path):
        """Returns True when any name in the list is present."""
        (tmp_path / ".git").mkdir()
        ts_file = tmp_path / "app.ts"
        ts_file.touch()
        (tmp_path / "eslint.config.mjs").touch()
        assert _find_config_up(str(ts_file), [".eslintrc", "eslint.config.mjs"]) is True

    def test_returns_false_for_empty_config_names(self, tmp_path):
        """Empty config_names list → always returns False."""
        ts_file = tmp_path / "app.ts"
        ts_file.touch()
        assert _find_config_up(str(ts_file), []) is False

    def test_tsconfig_found_in_parent(self, tmp_path):
        """tsconfig.json in parent directory is discovered."""
        (tmp_path / ".git").mkdir()
        sub = tmp_path / "src"
        sub.mkdir()
        ts_file = sub / "component.ts"
        ts_file.touch()
        (tmp_path / "tsconfig.json").touch()
        assert _find_config_up(str(ts_file), ["tsconfig.json"]) is True

    def test_tsconfig_not_found_returns_false(self, tmp_path):
        """No tsconfig.json anywhere → returns False."""
        (tmp_path / ".git").mkdir()
        ts_file = tmp_path / "component.ts"
        ts_file.touch()
        assert _find_config_up(str(ts_file), ["tsconfig.json"]) is False


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
    def test_run_linters_typescript_success_no_config(self, tmp_path):
        """No eslint/tsconfig → only prettier runs, no errors."""
        (tmp_path / ".git").mkdir()
        ts_file = tmp_path / "app.ts"
        ts_file.touch()

        ok = MagicMock()
        ok.returncode = 0
        ok.stdout = ""
        ok.stderr = ""
        with patch("subprocess.run", return_value=ok) as mock_run:
            errors = run_linters(str(ts_file), "typescript")
        assert errors == []
        # Only prettier should have been called (1 command)
        assert mock_run.call_count == 1
        called_cmd = mock_run.call_args[0][0]
        assert called_cmd[0] == "prettier"

    def test_eslint_skipped_when_no_eslint_config(self, tmp_path):
        """No eslint config file → eslint command is not invoked."""
        (tmp_path / ".git").mkdir()
        ts_file = tmp_path / "app.ts"
        ts_file.touch()

        ok = MagicMock()
        ok.returncode = 0
        ok.stdout = ""
        ok.stderr = ""
        with patch("subprocess.run", return_value=ok) as mock_run:
            run_linters(str(ts_file), "typescript")

        invoked_tools = [call[0][0][0] for call in mock_run.call_args_list]
        assert "eslint" not in invoked_tools

    def test_tsc_skipped_when_no_tsconfig(self, tmp_path):
        """No tsconfig.json → tsc command is not invoked."""
        (tmp_path / ".git").mkdir()
        ts_file = tmp_path / "app.ts"
        ts_file.touch()

        ok = MagicMock()
        ok.returncode = 0
        ok.stdout = ""
        ok.stderr = ""
        with patch("subprocess.run", return_value=ok) as mock_run:
            run_linters(str(ts_file), "typescript")

        invoked_tools = [call[0][0][0] for call in mock_run.call_args_list]
        assert "tsc" not in invoked_tools

    def test_eslint_runs_when_eslint_config_present(self, tmp_path):
        """eslint config in project root → eslint is invoked."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".eslintrc.json").touch()
        ts_file = tmp_path / "app.ts"
        ts_file.touch()

        ok = MagicMock()
        ok.returncode = 0
        ok.stdout = ""
        ok.stderr = ""
        with patch("subprocess.run", return_value=ok) as mock_run:
            errors = run_linters(str(ts_file), "typescript")

        assert errors == []
        invoked_tools = [call[0][0][0] for call in mock_run.call_args_list]
        assert "eslint" in invoked_tools

    def test_tsc_runs_when_tsconfig_present(self, tmp_path):
        """tsconfig.json in project root → tsc is invoked."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "tsconfig.json").touch()
        ts_file = tmp_path / "app.ts"
        ts_file.touch()

        ok = MagicMock()
        ok.returncode = 0
        ok.stdout = ""
        ok.stderr = ""
        with patch("subprocess.run", return_value=ok) as mock_run:
            errors = run_linters(str(ts_file), "typescript")

        assert errors == []
        invoked_tools = [call[0][0][0] for call in mock_run.call_args_list]
        assert "tsc" in invoked_tools

    def test_eslint_failure_reported_when_config_present(self, tmp_path):
        """eslint exits non-zero → error is recorded."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".eslintrc.json").touch()
        ts_file = tmp_path / "app.ts"
        ts_file.touch()

        fail = MagicMock()
        fail.returncode = 1
        fail.stdout = "ESLint: no-unused-vars error"
        fail.stderr = ""

        ok = MagicMock()
        ok.returncode = 0
        ok.stdout = ""
        ok.stderr = ""

        # eslint (fail), prettier (ok)
        with patch("subprocess.run", side_effect=[fail, ok]):
            errors = run_linters(str(ts_file), "typescript")

        assert len(errors) > 0
        assert any("eslint" in e.lower() or "no-unused-vars" in e for e in errors)

    def test_eslint_config_mjs_detected(self, tmp_path):
        """eslint.config.mjs is recognised as a valid eslint config."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "eslint.config.mjs").touch()
        ts_file = tmp_path / "app.ts"
        ts_file.touch()

        ok = MagicMock()
        ok.returncode = 0
        ok.stdout = ""
        ok.stderr = ""
        with patch("subprocess.run", return_value=ok) as mock_run:
            run_linters(str(ts_file), "typescript")

        invoked_tools = [call[0][0][0] for call in mock_run.call_args_list]
        assert "eslint" in invoked_tools

    def test_both_eslint_and_tsc_run_when_both_configs_present(self, tmp_path):
        """Both configs present → all three tools (eslint, prettier, tsc) run."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".eslintrc.json").touch()
        (tmp_path / "tsconfig.json").touch()
        ts_file = tmp_path / "app.ts"
        ts_file.touch()

        ok = MagicMock()
        ok.returncode = 0
        ok.stdout = ""
        ok.stderr = ""
        with patch("subprocess.run", return_value=ok) as mock_run:
            errors = run_linters(str(ts_file), "typescript")

        assert errors == []
        invoked_tools = [call[0][0][0] for call in mock_run.call_args_list]
        assert "eslint" in invoked_tools
        assert "prettier" in invoked_tools
        assert "tsc" in invoked_tools
        assert mock_run.call_count == 3


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
        with patch("stratus.hooks.file_checker.run_linters", return_value=[]) as mock_linters:
            with pytest.raises(SystemExit) as exc_info:
                from stratus.hooks.file_checker import main

                main()
        assert exc_info.value.code == 0
        mock_linters.assert_called_once_with("foo.py", "python")

    def test_main_runs_linters_on_edit(self, monkeypatch):
        """tool_name=Edit → calls run_linters."""
        hook_data = {"tool_name": "Edit", "tool_input": {"file_path": "app.ts"}}
        monkeypatch.setattr("sys.stdin", self._make_stdin(hook_data))
        with patch("stratus.hooks.file_checker.run_linters", return_value=[]) as mock_linters:
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
        monkeypatch.setattr("sys.stdin", type("FakeStdin", (), {"read": lambda self: ""})())
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
