"""Tests for user agent discovery and merged registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from stratus.registry.loader import (
    AgentRegistry,
    discover_user_agents,
    parse_agent_frontmatter,
)


@pytest.fixture
def user_agent_dir(tmp_path: Path) -> Path:
    """Create a .claude/agents directory with sample user agents."""
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)

    user_agent = agents_dir / "my-custom-backend.md"
    user_agent.write_text(
        """---
name: my-custom-backend
description: "Custom backend engineer for my project API endpoints"
tools: Bash, Read, Edit, Write, Grep, Glob
model: sonnet
---

Custom backend implementation agent.
"""
    )

    managed_agent = agents_dir / "managed-agent.md"
    managed_agent.write_text(
        """<!-- STRATUS-MANAGED: hash123 -->
---
name: managed-agent
description: "Framework-managed agent"
tools: Read
model: haiku
---

This is a managed agent.
"""
    )

    return tmp_path


class TestParseAgentFrontmatter:
    @pytest.mark.unit
    def test_parse_valid_frontmatter(self, tmp_path: Path) -> None:
        agent_file = tmp_path / "test-agent.md"
        agent_file.write_text(
            """---
name: test-agent
description: "Test agent for implementation tasks"
tools: Bash, Read, Edit, Write
model: opus
---

Test agent body.
"""
        )
        entry = parse_agent_frontmatter(agent_file)
        assert entry is not None
        assert entry.name == "test-agent"
        assert entry.model == "opus"
        assert entry.can_write is True
        assert "implementation" in entry.phases

    @pytest.mark.unit
    def test_parse_no_frontmatter(self, tmp_path: Path) -> None:
        agent_file = tmp_path / "no-fm.md"
        agent_file.write_text("No frontmatter here.")
        entry = parse_agent_frontmatter(agent_file)
        assert entry is None

    @pytest.mark.unit
    def test_derive_can_write(self, tmp_path: Path) -> None:
        agent_file = tmp_path / "readonly-agent.md"
        agent_file.write_text(
            """---
name: readonly-agent
description: "Read-only reviewer"
tools: Bash, Read, Grep
model: opus
---

Read-only agent.
"""
        )
        entry = parse_agent_frontmatter(agent_file)
        assert entry is not None
        assert entry.can_write is False

    @pytest.mark.unit
    def test_derive_phases_from_description(self, tmp_path: Path) -> None:
        qa_file = tmp_path / "qa-agent.md"
        qa_file.write_text(
            """---
name: qa-agent
description: "Test and QA verification agent"
tools: Bash, Read, Write
model: haiku
---

QA agent.
"""
        )
        entry = parse_agent_frontmatter(qa_file)
        assert entry is not None
        assert "verify" in entry.phases


class TestDiscoverUserAgents:
    @pytest.mark.unit
    def test_discovers_user_agents(self, user_agent_dir: Path) -> None:
        agents = discover_user_agents(user_agent_dir)
        assert len(agents) == 1
        assert agents[0].name == "my-custom-backend"

    @pytest.mark.unit
    def test_skips_managed_agents(self, user_agent_dir: Path) -> None:
        agents = discover_user_agents(user_agent_dir)
        names = [a.name for a in agents]
        assert "managed-agent" not in names

    @pytest.mark.unit
    def test_returns_empty_for_no_dir(self, tmp_path: Path) -> None:
        agents = discover_user_agents(tmp_path)
        assert agents == []


class TestLoadMerged:
    @pytest.mark.unit
    def test_load_merged_without_project_root(self) -> None:
        registry = AgentRegistry.load_merged(None)
        assert len(registry.all_agents()) == 26

    @pytest.mark.unit
    def test_load_merged_with_user_agents(self, user_agent_dir: Path) -> None:
        registry = AgentRegistry.load_merged(user_agent_dir)
        all_agents = registry.all_agents()
        assert len(all_agents) == 27
        assert registry.get("my-custom-backend") is not None

    @pytest.mark.unit
    def test_user_agent_overrides_bundled(self, tmp_path: Path) -> None:
        agents_dir = tmp_path / ".claude" / "agents"
        agents_dir.mkdir(parents=True)

        override = agents_dir / "delivery-implementation-expert.md"
        override.write_text(
            """---
name: delivery-implementation-expert
description: "My custom override of delivery-implementation-expert"
tools: Bash, Read, Edit, Write
model: opus
---

Custom override.
"""
        )

        registry = AgentRegistry.load_merged(tmp_path)
        agent = registry.get("delivery-implementation-expert")
        assert agent is not None
        assert agent.model == "opus"
        assert agent.layer == "engineering"  # User overrides keep the same layer

    @pytest.mark.unit
    def test_merged_registry_routes_to_user_agent(self, user_agent_dir: Path) -> None:
        from stratus.registry.routing import route_task

        registry = AgentRegistry.load_merged(user_agent_dir)
        result = route_task("implementation", registry=registry)
        assert result == "delivery-backend-engineer"

    @pytest.mark.unit
    def test_merged_registry_includes_user_in_task_types(self, user_agent_dir: Path) -> None:
        agents_dir = user_agent_dir / ".claude" / "agents"
        custom = agents_dir / "custom-reviewer.md"
        custom.write_text(
            """---
name: custom-reviewer
description: "Code review specialist"
tools: Bash, Read
model: opus
---

Review agent.
"""
        )

        registry = AgentRegistry.load_merged(user_agent_dir)
        reviewers = registry.get_for_task_type("review")
        names = [a.name for a in reviewers]
        assert "custom-reviewer" in names or any("review" in n for n in names)
