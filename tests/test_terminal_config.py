import os
import pytest
from pathlib import Path


class TestTerminalConfig:
    def test_terminal_config_defaults(self):
        from stratus.terminal.config import TerminalConfig

        config = TerminalConfig()
        assert config.enabled is True
        assert config.default_shell == "/bin/bash"
        assert config.default_cols == 80
        assert config.default_rows == 24
        assert config.max_sessions == 5
        assert config.max_output_buffer == 1024 * 1024
        assert config.heartbeat_interval == 30

    def test_terminal_config_env_override_enabled(self, monkeypatch):
        from stratus.terminal.config import TerminalConfig

        monkeypatch.setenv("STRATUS_TERMINAL_ENABLED", "false")
        config = TerminalConfig.from_env()
        assert config.enabled is False

    def test_terminal_config_env_override_shell(self, monkeypatch):
        from stratus.terminal.config import TerminalConfig

        monkeypatch.setenv("STRATUS_TERMINAL_SHELL", "/bin/zsh")
        config = TerminalConfig.from_env()
        assert config.default_shell == "/bin/zsh"

    def test_terminal_config_env_override_cols_rows(self, monkeypatch):
        from stratus.terminal.config import TerminalConfig

        monkeypatch.setenv("STRATUS_TERMINAL_COLS", "120")
        monkeypatch.setenv("STRATUS_TERMINAL_ROWS", "40")
        config = TerminalConfig.from_env()
        assert config.default_cols == 120
        assert config.default_rows == 40

    def test_terminal_config_env_override_max_sessions(self, monkeypatch):
        from stratus.terminal.config import TerminalConfig

        monkeypatch.setenv("STRATUS_TERMINAL_MAX_SESSIONS", "10")
        config = TerminalConfig.from_env()
        assert config.max_sessions == 10

    def test_terminal_config_detect_shell_from_env(self, monkeypatch):
        from stratus.terminal.config import TerminalConfig

        monkeypatch.setenv("SHELL", "/usr/bin/fish")
        config = TerminalConfig.from_env()
        assert config.default_shell == "/usr/bin/fish"

    def test_terminal_config_detect_shell_fallback(self, monkeypatch):
        from stratus.terminal.config import TerminalConfig

        monkeypatch.delenv("SHELL", raising=False)
        config = TerminalConfig.from_env()
        assert config.default_shell == "/bin/bash"

    def test_terminal_config_from_ai_framework_json(self, tmp_path: Path):
        from stratus.terminal.config import TerminalConfig

        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text('{"terminal": {"enabled": false, "default_shell": "/bin/zsh"}}')

        config = TerminalConfig.from_file(config_file)
        assert config.enabled is False
        assert config.default_shell == "/bin/zsh"

    def test_terminal_config_file_missing_uses_defaults(self, tmp_path: Path):
        from stratus.terminal.config import TerminalConfig

        config_file = tmp_path / ".ai-framework.json"
        config = TerminalConfig.from_file(config_file)
        assert config.enabled is True
        assert config.default_shell == "/bin/bash"

    def test_terminal_config_env_overrides_file(self, tmp_path: Path, monkeypatch):
        from stratus.terminal.config import TerminalConfig

        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text('{"terminal": {"default_shell": "/bin/zsh"}}')

        monkeypatch.setenv("STRATUS_TERMINAL_SHELL", "/bin/fish")
        config = TerminalConfig.from_file(config_file)
        assert config.default_shell == "/bin/fish"
