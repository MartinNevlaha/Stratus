"""DeliveryConfig dataclass and loader for delivery framework settings."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from stratus.orchestration.delivery_models import OrchestrationMode


@dataclass
class DeliveryConfig:
    enabled: bool = False
    orchestration_mode: str = "classic"
    active_phases: list[str] = field(default_factory=list)
    disabled_invariants: list[str] = field(default_factory=list)
    disabled_agents: list[str] = field(default_factory=list)
    max_review_iterations: int = 3
    skip_performance: bool = True


def load_delivery_config(path: Path | None = None) -> DeliveryConfig:
    """Load delivery config from .ai-framework.json."""
    config = DeliveryConfig()
    if path and path.exists():
        try:
            data = json.loads(path.read_text())
            section = data.get("delivery_framework", {})
            if isinstance(section, dict):
                _apply(config, section)
        except (json.JSONDecodeError, OSError):
            pass
    # Env overrides
    if env_mode := os.environ.get("AI_FRAMEWORK_ORCHESTRATION_MODE"):
        try:
            _ = OrchestrationMode(env_mode)
            config.orchestration_mode = env_mode
        except ValueError:
            pass
    if env_enabled := os.environ.get("AI_FRAMEWORK_DELIVERY_ENABLED"):
        config.enabled = env_enabled.lower() in ("true", "1", "yes")
    return config


def _apply(config: DeliveryConfig, data: dict[str, object]) -> None:
    if "enabled" in data and isinstance(data["enabled"], bool):
        config.enabled = data["enabled"]
    if "orchestration_mode" in data and isinstance(data["orchestration_mode"], str):
        try:
            _ = OrchestrationMode(data["orchestration_mode"])
            config.orchestration_mode = data["orchestration_mode"]
        except ValueError:
            pass
    if "active_phases" in data and isinstance(data["active_phases"], list):
        config.active_phases = [p for p in data["active_phases"] if isinstance(p, str)]
    if "disabled_invariants" in data and isinstance(data["disabled_invariants"], list):
        config.disabled_invariants = [i for i in data["disabled_invariants"] if isinstance(i, str)]
    if "disabled_agents" in data and isinstance(data["disabled_agents"], list):
        config.disabled_agents = [a for a in data["disabled_agents"] if isinstance(a, str)]
    if "max_review_iterations" in data and isinstance(data["max_review_iterations"], int):
        config.max_review_iterations = data["max_review_iterations"]
    if "skip_performance" in data and isinstance(data["skip_performance"], bool):
        config.skip_performance = data["skip_performance"]
