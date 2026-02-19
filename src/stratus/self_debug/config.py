"""Configuration for the self-debug sandbox."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import cast


@dataclass
class SelfDebugConfig:
    enabled: bool = False
    max_patch_lines: int = 200
    max_issues: int = 50
    analyze_tests: bool = False


def load_self_debug_config(path: Path | None) -> SelfDebugConfig:
    """Load self-debug config from .ai-framework.json with env var overrides."""
    config = SelfDebugConfig()

    if path and path.exists():
        try:
            text = path.read_text()
            if text.strip():
                raw: dict[str, object] = json.loads(text)  # pyright: ignore[reportAny]
                self_debug: object = raw.get("self_debug", {})
                if isinstance(self_debug, dict):
                    _apply_self_debug(config, cast("dict[str, object]", self_debug))
        except (json.JSONDecodeError, OSError):
            pass

    # Env var overrides
    env_enabled = os.environ.get("AI_FRAMEWORK_SELF_DEBUG_ENABLED")
    if env_enabled is not None:
        config.enabled = env_enabled.lower() == "true"

    return config


def _apply_self_debug(cfg: SelfDebugConfig, data: dict[str, object]) -> None:
    if "enabled" in data and isinstance(data["enabled"], bool):
        cfg.enabled = data["enabled"]
    if "max_patch_lines" in data and isinstance(data["max_patch_lines"], int):
        cfg.max_patch_lines = data["max_patch_lines"]
    if "max_issues" in data and isinstance(data["max_issues"], int):
        cfg.max_issues = data["max_issues"]
    if "analyze_tests" in data and isinstance(data["analyze_tests"], bool):
        cfg.analyze_tests = data["analyze_tests"]
