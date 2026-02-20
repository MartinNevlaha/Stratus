"""Tests for orchestration/teams.py — TeamManager config, prompts, validation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from stratus.orchestration.models import (
    OrchestratorMode,
    PlanStatus,
    SpecPhase,
    SpecState,
    TeamConfig,
    TeammateInfo,
    TeamState,
)
from stratus.orchestration.teams import TeamManager


@pytest.fixture
def task_tool_config() -> TeamConfig:
    return TeamConfig(name="test", mode=OrchestratorMode.TASK_TOOL)


@pytest.fixture
def agent_teams_config() -> TeamConfig:
    return TeamConfig(
        name="review-team",
        mode=OrchestratorMode.AGENT_TEAMS,
        teammate_mode="auto",
        require_plan_approval=True,
        max_teammates=5,
    )


@pytest.fixture
def spec_state() -> SpecState:
    return SpecState(
        phase=SpecPhase.VERIFY,
        slug="my-feature",
        plan_path="/plans/feature.md",
        plan_status=PlanStatus.VERIFYING,
        total_tasks=5,
        completed_tasks=5,
    )


# ---------------------------------------------------------------------------
# Config queries
# ---------------------------------------------------------------------------


class TestConfigQueries:
    def test_is_enabled_task_tool(self, task_tool_config: TeamConfig):
        tm = TeamManager(task_tool_config)
        assert tm.is_enabled() is False

    def test_is_enabled_agent_teams(self, agent_teams_config: TeamConfig):
        tm = TeamManager(agent_teams_config)
        assert tm.is_enabled() is True

    def test_get_mode(self, task_tool_config: TeamConfig):
        tm = TeamManager(task_tool_config)
        assert tm.get_mode() == OrchestratorMode.TASK_TOOL

    def test_get_mode_agent_teams(self, agent_teams_config: TeamConfig):
        tm = TeamManager(agent_teams_config)
        assert tm.get_mode() == OrchestratorMode.AGENT_TEAMS


# ---------------------------------------------------------------------------
# Prompt generation
# ---------------------------------------------------------------------------


class TestPromptGeneration:
    def test_build_team_prompt_contains_agents(
        self, agent_teams_config: TeamConfig, spec_state: SpecState
    ):
        tm = TeamManager(agent_teams_config)
        prompt = tm.build_team_prompt(
            spec_state, ["delivery-spec-reviewer-compliance", "delivery-spec-reviewer-quality"]
        )
        assert "delivery-spec-reviewer-compliance" in prompt
        assert "delivery-spec-reviewer-quality" in prompt

    def test_build_team_prompt_contains_slug(
        self, agent_teams_config: TeamConfig, spec_state: SpecState
    ):
        tm = TeamManager(agent_teams_config)
        prompt = tm.build_team_prompt(spec_state, ["reviewer"])
        assert "my-feature" in prompt

    def test_build_review_team_prompt(self, agent_teams_config: TeamConfig, spec_state: SpecState):
        tm = TeamManager(agent_teams_config)
        prompt = tm.build_review_team_prompt(spec_state)
        assert "review" in prompt.lower()
        assert "spec-reviewer-compliance" in prompt
        assert "spec-reviewer-quality" in prompt

    def test_build_implement_team_prompt(
        self, agent_teams_config: TeamConfig, spec_state: SpecState
    ):
        tm = TeamManager(agent_teams_config)
        tasks = [
            {"id": 1, "description": "Implement auth module"},
            {"id": 2, "description": "Implement billing module"},
        ]
        prompt = tm.build_implement_team_prompt(spec_state, tasks)
        assert "auth module" in prompt.lower()
        assert "billing module" in prompt.lower()

    def test_build_team_prompt_includes_plan_approval(
        self, agent_teams_config: TeamConfig, spec_state: SpecState
    ):
        tm = TeamManager(agent_teams_config)
        prompt = tm.build_team_prompt(spec_state, ["reviewer"])
        assert "plan" in prompt.lower()

    def test_build_team_prompt_no_plan_approval(self, spec_state: SpecState):
        config = TeamConfig(
            name="no-plan",
            mode=OrchestratorMode.AGENT_TEAMS,
            require_plan_approval=False,
        )
        tm = TeamManager(config)
        prompt = tm.build_team_prompt(spec_state, ["reviewer"])
        assert "plan approval" not in prompt.lower()

    def test_build_team_prompt_delegate_mode(self, spec_state: SpecState):
        config = TeamConfig(
            name="delegate",
            mode=OrchestratorMode.AGENT_TEAMS,
            delegate_mode=True,
        )
        tm = TeamManager(config)
        prompt = tm.build_team_prompt(spec_state, ["impl-1"])
        assert "delegate" in prompt.lower()


# ---------------------------------------------------------------------------
# Team state reading
# ---------------------------------------------------------------------------


class TestTeamState:
    def test_read_team_state_missing(self, task_tool_config: TeamConfig, tmp_path: Path):
        tm = TeamManager(task_tool_config)
        result = tm.read_team_state("nonexistent", teams_dir=tmp_path)
        assert result is None

    def test_read_team_state_valid(self, task_tool_config: TeamConfig, tmp_path: Path):
        team_dir = tmp_path / "teams" / "my-team"
        team_dir.mkdir(parents=True)
        state = TeamState(
            config=TeamConfig(name="my-team"),
            teammates=[TeammateInfo(name="t1", agent_type="qa")],
        )
        (team_dir / "config.json").write_text(json.dumps(state.model_dump()))

        tm = TeamManager(task_tool_config)
        result = tm.read_team_state("my-team", teams_dir=tmp_path / "teams")
        assert result is not None
        assert result.config.name == "my-team"
        assert len(result.teammates) == 1

    def test_read_team_state_corrupt_json(self, task_tool_config: TeamConfig, tmp_path: Path):
        team_dir = tmp_path / "teams" / "bad"
        team_dir.mkdir(parents=True)
        (team_dir / "config.json").write_text("not json")

        tm = TeamManager(task_tool_config)
        result = tm.read_team_state("bad", teams_dir=tmp_path / "teams")
        assert result is None

    def test_list_teammates_empty(self, task_tool_config: TeamConfig, tmp_path: Path):
        tm = TeamManager(task_tool_config)
        result = tm.list_teammates("nonexistent", teams_dir=tmp_path)
        assert result == []


# ---------------------------------------------------------------------------
# Environment validation
# ---------------------------------------------------------------------------


class TestEnvironmentValidation:
    @patch.dict("os.environ", {}, clear=True)
    def test_validate_missing_env_var(self, agent_teams_config: TeamConfig):
        tm = TeamManager(agent_teams_config)
        ok, reason = tm.validate_team_environment()
        assert ok is False
        assert "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" in reason

    @patch.dict("os.environ", {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}, clear=True)
    def test_validate_env_var_present(self, agent_teams_config: TeamConfig):
        tm = TeamManager(agent_teams_config)
        ok, reason = tm.validate_team_environment()
        assert ok is True

    def test_validate_task_tool_mode_always_ok(self, task_tool_config: TeamConfig):
        tm = TeamManager(task_tool_config)
        ok, reason = tm.validate_team_environment()
        assert ok is True

    @patch.dict("os.environ", {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}, clear=True)
    def test_validate_invalid_teammate_mode(self):
        config = TeamConfig(
            name="bad",
            mode=OrchestratorMode.AGENT_TEAMS,
            teammate_mode="invalid",
        )
        tm = TeamManager(config)
        ok, reason = tm.validate_team_environment()
        assert ok is False
        assert "teammate_mode" in reason


# ---------------------------------------------------------------------------
# Quality gate helpers
# ---------------------------------------------------------------------------


class TestQualityGateHelpers:
    def test_validate_verdict_output_pass(self, task_tool_config: TeamConfig):
        tm = TeamManager(task_tool_config)
        ok, msg = tm.validate_verdict_output("Verdict: PASS\nNo issues found.")
        assert ok is True

    def test_validate_verdict_output_fail_with_findings(self, task_tool_config: TeamConfig):
        tm = TeamManager(task_tool_config)
        ok, msg = tm.validate_verdict_output(
            "Verdict: FAIL\n- must_fix: src/main.py:10 — Missing validation"
        )
        assert ok is True

    def test_validate_verdict_output_missing_verdict(self, task_tool_config: TeamConfig):
        tm = TeamManager(task_tool_config)
        ok, msg = tm.validate_verdict_output("Some random text without verdict")
        assert ok is False
        assert "verdict" in msg.lower()

    def test_validate_task_completion_valid(self, task_tool_config: TeamConfig):
        tm = TeamManager(task_tool_config)
        ok, msg = tm.validate_task_completion("task-1", "All tests pass.\n5 passed in 0.3s")
        assert ok is True

    def test_validate_task_completion_empty(self, task_tool_config: TeamConfig):
        tm = TeamManager(task_tool_config)
        ok, msg = tm.validate_task_completion("task-1", "")
        assert ok is False


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


class TestConfigLoading:
    def test_load_from_json(self, tmp_path: Path):
        config_data = {
            "agent_teams": {
                "enabled": True,
                "mode": "agent-teams",
                "teammate_mode": "tmux",
                "delegate_mode": True,
                "require_plan_approval": False,
                "max_teammates": 3,
            }
        }
        config_path = tmp_path / ".ai-framework.json"
        config_path.write_text(json.dumps(config_data))

        from stratus.orchestration.teams import load_team_config

        tc = load_team_config(config_path)
        assert tc.mode == OrchestratorMode.AGENT_TEAMS
        assert tc.teammate_mode == "tmux"
        assert tc.delegate_mode is True
        assert tc.require_plan_approval is False
        assert tc.max_teammates == 3

    def test_load_from_missing_file(self):
        from stratus.orchestration.teams import load_team_config

        tc = load_team_config(Path("/nonexistent"))
        assert tc.mode == OrchestratorMode.TASK_TOOL
        assert tc.max_teammates == 5

    def test_load_env_override(self, tmp_path: Path):
        from stratus.orchestration.teams import load_team_config

        config_path = tmp_path / ".ai-framework.json"
        config_path.write_text("{}")

        with patch.dict("os.environ", {"AI_FRAMEWORK_AGENT_TEAMS_ENABLED": "true"}):
            tc = load_team_config(config_path)
            assert tc.mode == OrchestratorMode.AGENT_TEAMS
