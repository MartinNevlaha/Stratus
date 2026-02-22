from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


def _safe_int(value: str, default: int) -> int:
    try:
        return int(value)
    except ValueError:
        return default


@dataclass
class TerminalConfig:
    enabled: bool = True
    default_shell: str = "/bin/bash"
    default_cols: int = 80
    default_rows: int = 24
    max_sessions: int = 5
    max_output_buffer: int = 1024 * 1024
    heartbeat_interval: int = 30

    @classmethod
    def from_env(cls) -> TerminalConfig:
        shell = os.environ.get("SHELL", "/bin/bash")

        enabled = os.environ.get("STRATUS_TERMINAL_ENABLED", "true").lower() != "false"
        env_shell = os.environ.get("STRATUS_TERMINAL_SHELL")
        cols = _safe_int(os.environ.get("STRATUS_TERMINAL_COLS", "80"), 80)
        rows = _safe_int(os.environ.get("STRATUS_TERMINAL_ROWS", "24"), 24)
        max_sessions = _safe_int(os.environ.get("STRATUS_TERMINAL_MAX_SESSIONS", "5"), 5)

        return cls(
            enabled=enabled,
            default_shell=env_shell if env_shell else shell,
            default_cols=cols,
            default_rows=rows,
            max_sessions=max_sessions,
        )

    @classmethod
    def from_file(cls, path: Path) -> TerminalConfig:
        config = cls.from_env()

        if not path.exists():
            return config

        try:
            data = json.loads(path.read_text())
            terminal_config = data.get("terminal", {})

            if "enabled" in terminal_config:
                config.enabled = terminal_config["enabled"]
            if "default_shell" in terminal_config:
                if not os.environ.get("STRATUS_TERMINAL_SHELL"):
                    config.default_shell = terminal_config["default_shell"]
            if "default_cols" in terminal_config:
                config.default_cols = terminal_config["default_cols"]
            if "default_rows" in terminal_config:
                config.default_rows = terminal_config["default_rows"]
            if "max_sessions" in terminal_config:
                config.max_sessions = terminal_config["max_sessions"]

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load terminal config from {path}: {e}")

        return config


def load_terminal_config(path: Path | None = None) -> TerminalConfig:
    if path is None:
        path = Path.cwd() / ".ai-framework.json"
    return TerminalConfig.from_file(path)
