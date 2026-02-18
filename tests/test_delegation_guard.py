"""Tests for the delegation guard hook."""

from __future__ import annotations

from stratus.hooks.delegation_guard import _is_allowed_file, evaluate_guard


class TestIsAllowedFile:
    def test_markdown_allowed(self):
        assert _is_allowed_file("README.md") is True

    def test_json_allowed(self):
        assert _is_allowed_file("config.json") is True

    def test_yaml_allowed(self):
        assert _is_allowed_file("docker-compose.yaml") is True

    def test_yml_allowed(self):
        assert _is_allowed_file("config.yml") is True

    def test_toml_allowed(self):
        assert _is_allowed_file("pyproject.toml") is True

    def test_python_not_allowed(self):
        assert _is_allowed_file("src/main.py") is False

    def test_typescript_not_allowed(self):
        assert _is_allowed_file("src/app.ts") is False

    def test_dotfile_allowed(self):
        assert _is_allowed_file(".gitignore") is True

    def test_empty_not_allowed(self):
        assert _is_allowed_file("") is False

    def test_cfg_allowed(self):
        assert _is_allowed_file("setup.cfg") is True


class TestEvaluateGuard:
    def test_non_write_tool_passes(self):
        code, msg = evaluate_guard("Read", "src/main.py", "verify")
        assert code == 0
        assert msg == ""

    def test_no_phase_passes(self):
        code, msg = evaluate_guard("Write", "src/main.py", None)
        assert code == 0
        assert msg == ""

    def test_doc_file_always_passes(self):
        code, msg = evaluate_guard("Write", "docs/README.md", "verify")
        assert code == 0
        assert msg == ""

    def test_config_file_always_passes(self):
        code, msg = evaluate_guard("Edit", "config.json", "verify")
        assert code == 0
        assert msg == ""

    def test_verify_phase_blocks_write(self):
        code, msg = evaluate_guard("Write", "src/main.py", "verify")
        assert code == 2
        assert "blocked" in msg.lower()
        assert "VERIFY" in msg

    def test_verify_phase_blocks_edit(self):
        code, msg = evaluate_guard("Edit", "src/handler.py", "verify")
        assert code == 2

    def test_verify_phase_blocks_notebook(self):
        code, msg = evaluate_guard("NotebookEdit", "notebook.ipynb", "verify")
        assert code == 2

    def test_implement_phase_warns(self):
        code, msg = evaluate_guard("Write", "src/main.py", "implement")
        assert code == 0
        assert "delegation reminder" in msg.lower()

    def test_implementation_phase_warns(self):
        code, msg = evaluate_guard("Write", "src/main.py", "implementation")
        assert code == 0
        assert "delegation reminder" in msg.lower()

    def test_other_phase_passes(self):
        code, msg = evaluate_guard("Write", "src/main.py", "plan")
        assert code == 0
        assert msg == ""

    def test_none_file_path_verify(self):
        code, msg = evaluate_guard("Write", None, "verify")
        assert code == 2

    def test_none_file_path_no_phase(self):
        code, msg = evaluate_guard("Write", None, None)
        assert code == 0
