"""Configuration for the skills system."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SkillsConfig:
    enabled: bool = True
    auto_dispatch: bool = True
    skills_dir: str = ".claude/skills"


def load_skills_config(path: Path | None = None) -> SkillsConfig:
    """Load skills config from .ai-framework.json."""
    config = SkillsConfig()
    if path and path.exists():
        try:
            data = json.loads(path.read_text())
            section = data.get("skills", {})
            if isinstance(section, dict):
                _apply(config, section)
        except (json.JSONDecodeError, OSError):
            pass
    if env_enabled := os.environ.get("AI_FRAMEWORK_SKILLS_ENABLED"):
        config.enabled = env_enabled.lower() in ("true", "1", "yes")
    return config


def _apply(config: SkillsConfig, data: dict[str, object]) -> None:
    if "enabled" in data and isinstance(data["enabled"], bool):
        config.enabled = data["enabled"]
    if "auto_dispatch" in data and isinstance(data["auto_dispatch"], bool):
        config.auto_dispatch = data["auto_dispatch"]
    if "skills_dir" in data and isinstance(data["skills_dir"], str):
        config.skills_dir = data["skills_dir"]
