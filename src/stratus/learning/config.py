"""Configuration for the adaptive learning layer with anti-annoyance controls."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from stratus.learning.models import Sensitivity

SENSITIVITY_CONFIDENCE_MAP: dict[Sensitivity, float] = {
    Sensitivity.CONSERVATIVE: 0.7,
    Sensitivity.MODERATE: 0.5,
    Sensitivity.AGGRESSIVE: 0.3,
}


@dataclass
class LearningConfig:
    global_enabled: bool = False
    sensitivity: Sensitivity = Sensitivity.CONSERVATIVE
    max_proposals_per_session: int = 3
    cooldown_days: int = 7
    batch_frequency: str = "session_end"
    commit_batch_threshold: int = 5
    min_age_hours: int = 24

    @property
    def min_confidence(self) -> float:
        return SENSITIVITY_CONFIDENCE_MAP[self.sensitivity]


def load_learning_config(path: Path | None) -> LearningConfig:
    """Load learning config from .ai-framework.json with env var overrides."""
    config = LearningConfig()

    if path and path.exists():
        try:
            text = path.read_text()
            if text.strip():
                data = json.loads(text)
                learning = data.get("learning", {})
                _apply_learning(config, learning)
        except (json.JSONDecodeError, OSError):
            pass

    # Env var overrides
    env_enabled = os.environ.get("AI_FRAMEWORK_LEARNING_ENABLED")
    if env_enabled is not None:
        config.global_enabled = env_enabled.lower() == "true"

    return config


def _apply_learning(cfg: LearningConfig, data: dict) -> None:
    if "global_enabled" in data:
        cfg.global_enabled = data["global_enabled"]
    if "sensitivity" in data:
        cfg.sensitivity = Sensitivity(data["sensitivity"])
    if "max_proposals_per_session" in data:
        cfg.max_proposals_per_session = data["max_proposals_per_session"]
    if "cooldown_days" in data:
        cfg.cooldown_days = data["cooldown_days"]
    if "batch_frequency" in data:
        cfg.batch_frequency = data["batch_frequency"]
    if "commit_batch_threshold" in data:
        cfg.commit_batch_threshold = data["commit_batch_threshold"]
    if "min_age_hours" in data:
        cfg.min_age_hours = data["min_age_hours"]
