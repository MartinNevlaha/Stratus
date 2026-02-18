"""Tests for tdd_enforcer PostToolUse hook."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from stratus.hooks.tdd_enforcer import find_test_file, is_skippable, main


class TestIsSkippable:
    def test_is_skippable_test_file(self):
        assert is_skippable("tests/test_foo.py") is True

    def test_is_skippable_test_file_prefix(self):
        assert is_skippable("test_bar.py") is True

    def test_is_skippable_test_suffix(self):
        assert is_skippable("bar_test.py") is True

    def test_is_skippable_test_dot_extension(self):
        assert is_skippable("component.test.ts") is True

    def test_is_skippable_spec_extension(self):
        assert is_skippable("service.spec.js") is True

    def test_is_skippable_conftest(self):
        assert is_skippable("tests/conftest.py") is True

    def test_is_skippable_markdown(self):
        assert is_skippable("README.md") is True

    def test_is_skippable_json(self):
        assert is_skippable("config.json") is True

    def test_is_skippable_yaml(self):
        assert is_skippable("settings.yaml") is True

    def test_is_skippable_yml(self):
        assert is_skippable("docker-compose.yml") is True

    def test_is_skippable_toml(self):
        assert is_skippable("pyproject.toml") is True

    def test_is_skippable_txt(self):
        assert is_skippable("requirements.txt") is True

    def test_is_skippable_cfg(self):
        assert is_skippable("setup.cfg") is True

    def test_is_skippable_ini(self):
        assert is_skippable("mypy.ini") is True

    def test_is_skippable_init(self):
        assert is_skippable("src/stratus/__init__.py") is True

    def test_is_skippable_main(self):
        assert is_skippable("src/stratus/__main__.py") is True

    def test_is_skippable_implementation(self):
        assert is_skippable("src/stratus/memory/database.py") is False

    def test_is_skippable_implementation_top_level(self):
        assert is_skippable("src/stratus/transcript.py") is False


class TestFindTestFile:
    def test_find_test_file_exists(self, tmp_path):
        # Create tests/test_bar.py
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_bar.py"
        test_file.write_text("# test")

        # find_test_file looks for tests/test_<stem>.py relative to cwd
        result = find_test_file("src/pkg/bar.py", project_root=tmp_path)
        assert result == test_file

    def test_find_test_file_missing(self, tmp_path):
        # No tests directory or test file
        result = find_test_file("src/pkg/bar.py", project_root=tmp_path)
        assert result is None

    def test_find_test_file_nested_module(self, tmp_path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_database.py"
        test_file.write_text("# test")

        result = find_test_file("src/stratus/memory/database.py", project_root=tmp_path)
        assert result == test_file

    def test_find_test_file_top_level_src(self, tmp_path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_transcript.py"
        test_file.write_text("# test")

        result = find_test_file("src/stratus/transcript.py", project_root=tmp_path)
        assert result == test_file


class TestMain:
    def _make_stdin(self, data: dict):
        """Return a stdin-like object returning JSON of data."""
        return type("FakeStdin", (), {"read": lambda self: json.dumps(data)})()

    def test_main_skips_non_write(self, monkeypatch):
        hook_input = {"tool_name": "Read", "tool_input": {"file_path": "src/foo.py"}}
        monkeypatch.setattr("sys.stdin", self._make_stdin(hook_input))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_main_skips_test_files(self, monkeypatch):
        hook_input = {
            "tool_name": "Write",
            "tool_input": {"file_path": "tests/test_foo.py"},
        }
        monkeypatch.setattr("sys.stdin", self._make_stdin(hook_input))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_main_skips_markdown(self, monkeypatch):
        hook_input = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "docs/README.md"},
        }
        monkeypatch.setattr("sys.stdin", self._make_stdin(hook_input))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_main_warns_no_test(self, monkeypatch, tmp_path, capsys):
        hook_input = {
            "tool_name": "Write",
            "tool_input": {"file_path": "src/stratus/foo.py"},
        }
        monkeypatch.setattr("sys.stdin", self._make_stdin(hook_input))
        with patch(
            "stratus.hooks.tdd_enforcer.find_test_file", return_value=None
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "test" in captured.err.lower() or "tdd" in captured.err.lower()

    def test_main_exits_0_when_test_exists(self, monkeypatch, tmp_path):
        hook_input = {
            "tool_name": "Write",
            "tool_input": {"file_path": "src/stratus/foo.py"},
        }
        monkeypatch.setattr("sys.stdin", self._make_stdin(hook_input))
        fake_test_path = tmp_path / "tests" / "test_foo.py"
        with patch(
            "stratus.hooks.tdd_enforcer.find_test_file", return_value=fake_test_path
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 0

    def test_main_exits_0_on_empty_input(self, monkeypatch):
        monkeypatch.setattr(
            "sys.stdin", type("FakeStdin", (), {"read": lambda self: "{}"})()
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_main_skips_non_python_implementation(self, monkeypatch):
        hook_input = {
            "tool_name": "Write",
            "tool_input": {"file_path": "src/stratus/styles.css"},
        }
        monkeypatch.setattr("sys.stdin", self._make_stdin(hook_input))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_main_records_missing_test_on_exit_2(self, monkeypatch):
        """On missing test, _record_missing_test posts to analytics before exit 2."""
        hook_input = {
            "tool_name": "Write",
            "tool_input": {"file_path": "src/stratus/foo.py"},
        }
        monkeypatch.setattr("sys.stdin", self._make_stdin(hook_input))
        with patch("stratus.hooks.tdd_enforcer.find_test_file", return_value=None):
            with patch("stratus.hooks.tdd_enforcer.httpx") as mock_httpx:
                with pytest.raises(SystemExit) as exc_info:
                    main()
        assert exc_info.value.code == 2
        mock_httpx.post.assert_called_once()
        call_kwargs = mock_httpx.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["category"] == "missing_test"
        assert "foo.py" in payload["file_path"]
