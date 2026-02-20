"""Tests for AgentRegistry loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stratus.registry.loader import AgentRegistry
from stratus.registry.models import AgentEntry

TOTAL_AGENTS = 26
CORE_AGENTS = 7  # orchestration_modes == ["default"]
SWORM_AGENTS = 19  # orchestration_modes includes "sworm"


@pytest.mark.unit
def test_load_from_package():
    """AgentRegistry.load() returns all 26 agents from bundled JSON."""
    registry = AgentRegistry.load()
    assert len(registry.all_agents()) == TOTAL_AGENTS


@pytest.mark.unit
def test_all_agents_count():
    """all_agents() returns exactly 26 agents."""
    registry = AgentRegistry.load()
    agents = registry.all_agents()
    assert len(agents) == TOTAL_AGENTS
    assert all(isinstance(a, AgentEntry) for a in agents)


@pytest.mark.unit
def test_get_by_name():
    """get() returns the correct AgentEntry for a known agent name."""
    registry = AgentRegistry.load()
    agent = registry.get("framework-expert")
    assert agent is not None
    assert agent.name == "framework-expert"
    assert agent.model == "sonnet"
    assert agent.can_write is True
    assert agent.layer == "core"


@pytest.mark.unit
def test_get_unknown_returns_none():
    """get() returns None for an unknown agent name."""
    registry = AgentRegistry.load()
    assert registry.get("does-not-exist") is None
    assert registry.get("") is None


@pytest.mark.unit
def test_filter_by_mode_default():
    """filter_by_mode('default') returns exactly 7 core agents."""
    registry = AgentRegistry.load()
    agents = registry.filter_by_mode("default")
    assert len(agents) == CORE_AGENTS
    for agent in agents:
        assert "default" in agent.orchestration_modes


@pytest.mark.unit
def test_filter_by_mode_sworm():
    """filter_by_mode('sworm') returns exactly 19 delivery agents."""
    registry = AgentRegistry.load()
    agents = registry.filter_by_mode("sworm")
    assert len(agents) == SWORM_AGENTS
    for agent in agents:
        assert "sworm" in agent.orchestration_modes


@pytest.mark.unit
def test_filter_by_phase_implement():
    """filter_by_phase('implement') returns implementation-phase agents."""
    registry = AgentRegistry.load()
    agents = registry.filter_by_phase("implement")
    assert len(agents) >= 1
    names = [a.name for a in agents]
    assert "framework-expert" in names
    for agent in agents:
        assert "implement" in agent.phases


@pytest.mark.unit
def test_filter_by_phase_verify():
    """filter_by_phase('verify') returns review/QA phase agents."""
    registry = AgentRegistry.load()
    agents = registry.filter_by_phase("verify")
    assert len(agents) >= 2
    names = [a.name for a in agents]
    assert "qa-engineer" in names
    assert "spec-reviewer-compliance" in names
    for agent in agents:
        assert "verify" in agent.phases


@pytest.mark.unit
def test_filter_by_phase_implementation():
    """filter_by_phase('implementation') returns delivery engineering agents."""
    registry = AgentRegistry.load()
    agents = registry.filter_by_phase("implementation")
    assert len(agents) >= 1
    names = [a.name for a in agents]
    assert "delivery-backend-engineer" in names


@pytest.mark.unit
def test_get_writers():
    """get_writers() returns agents with can_write=True."""
    registry = AgentRegistry.load()
    writers = registry.get_writers()
    assert len(writers) >= 1
    for agent in writers:
        assert agent.can_write is True
    names = [a.name for a in writers]
    assert "framework-expert" in names


@pytest.mark.unit
def test_get_writers_mode_filtered():
    """get_writers(mode='default') returns only core writers."""
    registry = AgentRegistry.load()
    writers = registry.get_writers(mode="default")
    assert len(writers) >= 1
    for agent in writers:
        assert agent.can_write is True
        assert "default" in agent.orchestration_modes
    # Core read-only agents should NOT appear
    names = [a.name for a in writers]
    assert "architecture-guide" not in names
    assert "plan-verifier" not in names


@pytest.mark.unit
def test_get_for_task_type():
    """get_for_task_type() returns agents matching the task type."""
    registry = AgentRegistry.load()
    impl_agents = registry.get_for_task_type("implementation")
    assert len(impl_agents) >= 1
    for agent in impl_agents:
        assert "implementation" in agent.task_types

    test_agents = registry.get_for_task_type("test")
    assert len(test_agents) >= 1
    names = [a.name for a in test_agents]
    assert "qa-engineer" in names


@pytest.mark.unit
def test_get_for_task_type_unknown():
    """get_for_task_type() returns empty list for unknown task type."""
    registry = AgentRegistry.load()
    result = registry.get_for_task_type("nonexistent-task-type")
    assert result == []


@pytest.mark.unit
def test_phase_leads():
    """get_phase_lead() returns correct stripped lead name."""
    registry = AgentRegistry.load()
    # delivery-product-owner → product-owner
    assert registry.get_phase_lead("discovery") == "product-owner"
    # delivery-tpm → tpm
    assert registry.get_phase_lead("planning") == "tpm"
    # architecture-guide (no prefix) → architecture-guide
    assert registry.get_phase_lead("plan") == "architecture-guide"
    # framework-expert (no prefix) → framework-expert
    assert registry.get_phase_lead("implement") == "framework-expert"


@pytest.mark.unit
def test_phase_lead_unknown_returns_none():
    """get_phase_lead() returns None for unknown phase."""
    registry = AgentRegistry.load()
    assert registry.get_phase_lead("nonexistent-phase") is None


@pytest.mark.unit
def test_phase_roles():
    """get_phase_roles() returns role names without 'delivery-' prefix."""
    registry = AgentRegistry.load()
    roles = registry.get_phase_roles("implementation")
    assert len(roles) >= 1
    # Should not include 'delivery-' prefix
    for role in roles:
        assert not role.startswith("delivery-")
    assert "backend-engineer" in roles


@pytest.mark.unit
def test_phase_roles_discovery():
    """get_phase_roles('discovery') returns sworm-mode agents for discovery."""
    registry = AgentRegistry.load()
    roles = registry.get_phase_roles("discovery")
    assert len(roles) >= 1
    # All results should be from sworm-mode agents
    for role in roles:
        assert not role.startswith("delivery-")


@pytest.mark.unit
def test_from_json(tmp_path: Path):
    """from_json() loads registry from an explicit file path."""
    data = {
        "version": 1,
        "phase_leads": {"implement": "framework-expert"},
        "agents": [
            {
                "name": "framework-expert",
                "filename": "framework-expert.md",
                "model": "sonnet",
                "can_write": True,
                "layer": "core",
                "phases": ["implement"],
                "orchestration_modes": ["default"],
            }
        ],
    }
    json_file = tmp_path / "test-registry.json"
    json_file.write_text(json.dumps(data))

    registry = AgentRegistry.from_json(json_file)
    assert len(registry.all_agents()) == 1
    agent = registry.get("framework-expert")
    assert agent is not None
    assert agent.model == "sonnet"
    assert registry.get_phase_lead("implement") == "framework-expert"


@pytest.mark.unit
def test_from_json_missing_phase_leads(tmp_path: Path):
    """from_json() handles missing phase_leads gracefully."""
    data = {
        "version": 1,
        "agents": [
            {
                "name": "test-agent",
                "filename": "test-agent.md",
                "model": "haiku",
                "can_write": False,
                "layer": "core",
                "phases": ["verify"],
                "orchestration_modes": ["default"],
            }
        ],
    }
    json_file = tmp_path / "no-leads.json"
    json_file.write_text(json.dumps(data))

    registry = AgentRegistry.from_json(json_file)
    assert registry.get_phase_lead("verify") is None


@pytest.mark.unit
def test_filter_by_stack_universal():
    """filter_by_stack includes universal agents (applicable_stacks=None)."""
    registry = AgentRegistry.load()
    # Universal non-optional agents should appear regardless of stack
    result = registry.filter_by_stack({"python"})
    names = [a.name for a in result]
    assert "delivery-tpm" in names
    assert "delivery-risk-officer" in names


@pytest.mark.unit
def test_filter_by_stack_stack_specific():
    """filter_by_stack includes stack-specific agents when stack matches."""
    registry = AgentRegistry.load()
    result = registry.filter_by_stack({"python"})
    names = [a.name for a in result]
    assert "delivery-backend-engineer" in names
    # frontend engineer applies only to nextjs/react_native
    assert "delivery-frontend-engineer" not in names


@pytest.mark.unit
def test_filter_by_stack_excludes_optional_by_default():
    """filter_by_stack excludes optional agents when enabled_phases is None."""
    registry = AgentRegistry.load()
    result = registry.filter_by_stack({"python"})
    names = [a.name for a in result]
    # optional agents excluded when no enabled_phases given
    assert "delivery-product-owner" not in names
    assert "delivery-strategic-architect" not in names


@pytest.mark.unit
def test_delivery_agent_names_consistent():
    """All delivery agents have 'delivery-' prefix in their name."""
    registry = AgentRegistry.load()
    sworm = registry.filter_by_mode("sworm")
    for agent in sworm:
        assert agent.name.startswith("delivery-"), f"{agent.name} should start with delivery-"


@pytest.mark.unit
def test_core_agents_have_default_mode():
    """All core agents (layer=core) are in default orchestration mode."""
    registry = AgentRegistry.load()
    core_agents = [a for a in registry.all_agents() if a.layer == "core"]
    assert len(core_agents) == CORE_AGENTS
    for agent in core_agents:
        assert "default" in agent.orchestration_modes


@pytest.mark.unit
def test_all_agents_have_required_fields():
    """Every agent in registry has non-empty name, filename, model, layer, phases."""
    registry = AgentRegistry.load()
    for agent in registry.all_agents():
        assert agent.name, f"Agent missing name: {agent}"
        assert agent.filename, f"Agent missing filename: {agent}"
        assert agent.model in ("sonnet", "opus", "haiku"), f"Unknown model: {agent.model}"
        assert agent.layer in ("core", "process", "engineering"), f"Unknown layer: {agent.layer}"
        assert len(agent.phases) >= 1, f"Agent has no phases: {agent.name}"
        assert len(agent.orchestration_modes) >= 1, f"Agent has no modes: {agent.name}"
