"""Tests for AgentEntry Pydantic model."""

from __future__ import annotations

import pytest

from stratus.registry.models import AgentEntry


@pytest.mark.unit
def test_agent_entry_valid_data():
    """AgentEntry validates correctly with all fields."""
    entry = AgentEntry(
        name="framework-expert",
        filename="framework-expert.md",
        model="sonnet",
        can_write=True,
        layer="core",
        phases=["implement"],
        task_types=["implementation", "bug-fix"],
        applicable_stacks=None,
        orchestration_modes=["default"],
        optional=False,
        keywords=["implement", "build"],
    )
    assert entry.name == "framework-expert"
    assert entry.filename == "framework-expert.md"
    assert entry.model == "sonnet"
    assert entry.can_write is True
    assert entry.layer == "core"
    assert entry.phases == ["implement"]
    assert entry.task_types == ["implementation", "bug-fix"]
    assert entry.applicable_stacks is None
    assert entry.orchestration_modes == ["default"]
    assert entry.optional is False
    assert entry.keywords == ["implement", "build"]


@pytest.mark.unit
def test_agent_entry_defaults_empty_task_types():
    """AgentEntry defaults task_types to empty list."""
    entry = AgentEntry(
        name="test-agent",
        filename="test-agent.md",
        model="haiku",
        can_write=False,
        layer="core",
        phases=["plan"],
        orchestration_modes=["default"],
    )
    assert entry.task_types == []


@pytest.mark.unit
def test_agent_entry_defaults_empty_keywords():
    """AgentEntry defaults keywords to empty list."""
    entry = AgentEntry(
        name="test-agent",
        filename="test-agent.md",
        model="haiku",
        can_write=False,
        layer="core",
        phases=["plan"],
        orchestration_modes=["default"],
    )
    assert entry.keywords == []


@pytest.mark.unit
def test_agent_entry_defaults_optional_false():
    """AgentEntry defaults optional to False."""
    entry = AgentEntry(
        name="test-agent",
        filename="test-agent.md",
        model="sonnet",
        can_write=True,
        layer="core",
        phases=["implement"],
        orchestration_modes=["default"],
    )
    assert entry.optional is False


@pytest.mark.unit
def test_agent_entry_applicable_stacks_none():
    """AgentEntry accepts None for applicable_stacks (universal)."""
    entry = AgentEntry(
        name="test-agent",
        filename="test-agent.md",
        model="sonnet",
        can_write=True,
        layer="core",
        phases=["implement"],
        orchestration_modes=["default"],
        applicable_stacks=None,
    )
    assert entry.applicable_stacks is None


@pytest.mark.unit
def test_agent_entry_applicable_stacks_list():
    """AgentEntry accepts a list of stack names."""
    entry = AgentEntry(
        name="delivery-backend-engineer",
        filename="delivery-backend-engineer.md",
        model="sonnet",
        can_write=True,
        layer="engineering",
        phases=["implementation"],
        orchestration_modes=["sworm"],
        applicable_stacks=["nestjs", "python", "go", "rust"],
    )
    assert entry.applicable_stacks == ["nestjs", "python", "go", "rust"]


@pytest.mark.unit
def test_agent_entry_multiple_orchestration_modes():
    """AgentEntry supports multiple orchestration modes."""
    entry = AgentEntry(
        name="test-agent",
        filename="test-agent.md",
        model="sonnet",
        can_write=True,
        layer="core",
        phases=["implement"],
        orchestration_modes=["default", "sworm"],
    )
    assert "default" in entry.orchestration_modes
    assert "sworm" in entry.orchestration_modes


@pytest.mark.unit
def test_agent_entry_multiple_phases():
    """AgentEntry supports multiple phases."""
    entry = AgentEntry(
        name="delivery-tpm",
        filename="delivery-tpm.md",
        model="sonnet",
        can_write=False,
        layer="process",
        phases=["discovery", "planning", "implementation", "learning"],
        orchestration_modes=["sworm"],
    )
    assert len(entry.phases) == 4
    assert "planning" in entry.phases


@pytest.mark.unit
def test_agent_entry_model_validate():
    """AgentEntry.model_validate works from dict."""
    data = {
        "name": "qa-engineer",
        "filename": "qa-engineer.md",
        "model": "haiku",
        "can_write": True,
        "layer": "core",
        "phases": ["verify"],
        "orchestration_modes": ["default"],
    }
    entry = AgentEntry.model_validate(data)
    assert entry.name == "qa-engineer"
    assert entry.task_types == []
    assert entry.keywords == []
    assert entry.optional is False
    assert entry.applicable_stacks is None
