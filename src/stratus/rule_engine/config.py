"""RulesConfig dataclass and loader for rule engine settings."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RulesConfig:
    immutability_check: bool = True
    enforce_in_classic: bool = False


def load_rules_config(path: Path | None = None) -> RulesConfig:
    """Load rules config from .ai-framework.json."""
    config = RulesConfig()
    if path and path.exists():
        try:
            text = path.read_text()
            if text.strip():
                data = json.loads(text)
                section = data.get("rules", {})
                if isinstance(section, dict):
                    _apply(config, section)
        except (json.JSONDecodeError, OSError):
            pass
    if env_val := os.environ.get("AI_FRAMEWORK_RULES_IMMUTABILITY"):
        config.immutability_check = env_val.lower() in ("true", "1", "yes")
    return config


def _apply(cfg: RulesConfig, data: dict[str, object]) -> None:
    if "immutability_check" in data and isinstance(data["immutability_check"], bool):
        cfg.immutability_check = data["immutability_check"]
    if "enforce_in_classic" in data and isinstance(data["enforce_in_classic"], bool):
        cfg.enforce_in_classic = data["enforce_in_classic"]
