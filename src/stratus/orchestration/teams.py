"""Agent Teams integration: config, prompt generation, validation.

This module does NOT spawn teammates directly (that's done by the lead
via natural language). It provides config loading, team state tracking,
prompt templates, and quality gate validation helpers.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from stratus.orchestration.models import (
    OrchestratorMode,
    SpecState,
    TeamConfig,
    TeammateInfo,
    TeamState,
)

_VERDICT_RE = re.compile(r"verdict\s*:\s*(pass|fail)", re.IGNORECASE)
_VALID_TEAMMATE_MODES = {"auto", "in-process", "tmux"}


class TeamManager:
    """Manages Agent Teams lifecycle and configuration."""

    def __init__(self, config: TeamConfig) -> None:
        self._config = config

    # -- Config queries -----------------------------------------------------

    def is_enabled(self) -> bool:
        return self._config.mode == OrchestratorMode.AGENT_TEAMS

    def get_mode(self) -> OrchestratorMode:
        return self._config.mode

    # -- Prompt generation --------------------------------------------------

    def build_team_prompt(
        self, spec_state: SpecState, agents: list[str]
    ) -> str:
        lines = [
            f"Create a team for spec '{spec_state.slug}'.",
            f"Teammates: {', '.join(agents)}.",
        ]
        if self._config.delegate_mode:
            lines.append(
                "Enter delegate mode: restrict the lead to coordination-only tools."
            )
        if self._config.require_plan_approval:
            lines.append(
                "Require plan approval: teammates must get their plan approved "
                "before implementing."
            )
        if spec_state.plan_path:
            lines.append(f"Plan path: {spec_state.plan_path}")

        # Add registry validation warnings
        try:
            from stratus.registry.validation import validate_team_composition

            phase = spec_state.phase if hasattr(spec_state, "phase") else "implement"
            warnings = validate_team_composition(agents, phase)
            for w in warnings:
                lines.append(f"Warning: {w.message}")
        except ImportError:
            pass

        return "\n".join(lines)

    def build_review_team_prompt(self, spec_state: SpecState) -> str:
        reviewers = [
            "spec-reviewer-compliance",
            "spec-reviewer-quality",
        ]
        lines = [
            f"Create a review team for spec '{spec_state.slug}'.",
            f"Teammates: {', '.join(reviewers)}.",
            "Each reviewer should produce a verdict in format: 'Verdict: PASS' or 'Verdict: FAIL'.",
            "Findings should use: '- must_fix: ...', '- should_fix: ...', '- suggestion: ...'.",
        ]
        if self._config.require_plan_approval:
            lines.append(
                "Require plan approval: reviewers must get their plan approved "
                "before executing."
            )
        return "\n".join(lines)

    def build_implement_team_prompt(
        self, spec_state: SpecState, tasks: list[dict]
    ) -> str:
        lines = [
            f"Create an implementation team for spec '{spec_state.slug}'.",
            "Tasks:",
        ]
        for task in tasks:
            lines.append(f"  - Task {task.get('id', '?')}: {task.get('description', '')}")
        lines.append(
            "Each teammate should own non-overlapping files. "
            "Run tests after completing each task."
        )
        return "\n".join(lines)

    # -- Team state reading -------------------------------------------------

    def read_team_state(
        self, team_name: str, *, teams_dir: Path | None = None
    ) -> TeamState | None:
        if teams_dir is None:
            teams_dir = Path.home() / ".claude" / "teams"
        config_path = teams_dir / team_name / "config.json"
        try:
            data = json.loads(config_path.read_text())
            return TeamState(**data)
        except Exception:
            return None

    def list_teammates(
        self, team_name: str, *, teams_dir: Path | None = None
    ) -> list[TeammateInfo]:
        state = self.read_team_state(team_name, teams_dir=teams_dir)
        if state is None:
            return []
        return state.teammates

    # -- Environment validation ---------------------------------------------

    def validate_team_environment(self) -> tuple[bool, str]:
        if self._config.mode == OrchestratorMode.TASK_TOOL:
            return True, "Task tool mode requires no special environment"

        env_val = os.environ.get("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS")
        if env_val != "1":
            return False, (
                "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 must be set "
                "to use Agent Teams backend"
            )

        if self._config.teammate_mode not in _VALID_TEAMMATE_MODES:
            return False, (
                f"Invalid teammate_mode '{self._config.teammate_mode}'. "
                f"Valid modes: {sorted(_VALID_TEAMMATE_MODES)}"
            )

        return True, "Agent Teams environment is valid"

    # -- Quality gate helpers -----------------------------------------------

    def validate_verdict_output(self, output: str) -> tuple[bool, str]:
        if _VERDICT_RE.search(output):
            return True, "Verdict found"
        return False, "Output must contain 'Verdict: PASS' or 'Verdict: FAIL'"

    def validate_task_completion(
        self, task_id: str, output: str
    ) -> tuple[bool, str]:
        if not output.strip():
            return False, f"Task {task_id} produced empty output"
        return True, "Task output is non-empty"


# ---------------------------------------------------------------------------
# Config loading (follows learning/config.py pattern)
# ---------------------------------------------------------------------------


def load_team_config(path: Path | None = None) -> TeamConfig:
    """Load team config from .ai-framework.json with env var overrides."""
    config = TeamConfig()

    if path and path.exists():
        try:
            text = path.read_text()
            if text.strip():
                data = json.loads(text)
                teams = data.get("agent_teams", {})
                _apply_teams(config, teams)
        except (json.JSONDecodeError, OSError):
            pass

    # Env var override
    env_enabled = os.environ.get("AI_FRAMEWORK_AGENT_TEAMS_ENABLED")
    if env_enabled is not None and env_enabled.lower() == "true":
        config.mode = OrchestratorMode.AGENT_TEAMS

    return config


def _apply_teams(cfg: TeamConfig, data: dict) -> None:
    if "enabled" in data and data["enabled"]:
        cfg.mode = OrchestratorMode.AGENT_TEAMS
    if "mode" in data:
        cfg.mode = OrchestratorMode(data["mode"])
    if "teammate_mode" in data:
        cfg.teammate_mode = data["teammate_mode"]
    if "delegate_mode" in data:
        cfg.delegate_mode = data["delegate_mode"]
    if "require_plan_approval" in data:
        cfg.require_plan_approval = data["require_plan_approval"]
    if "max_teammates" in data:
        cfg.max_teammates = data["max_teammates"]
