"""AgentRegistry: load and query the unified agent registry."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from stratus.registry.models import AgentEntry


class AgentRegistry:
    """Unified agent registry loaded from agent-registry.json."""

    def __init__(self, agents: list[AgentEntry], phase_leads: dict[str, str]) -> None:
        self._agents = agents
        self._by_name: dict[str, AgentEntry] = {a.name: a for a in agents}
        self._phase_leads = phase_leads

    @classmethod
    def load(cls) -> AgentRegistry:
        """Load from bundled package data."""
        pkg = resources.files("stratus.registry")
        data = json.loads(pkg.joinpath("agent-registry.json").read_text(encoding="utf-8"))
        return cls._from_dict(data)

    @classmethod
    def from_json(cls, path: Path) -> AgentRegistry:
        """Load from explicit file path (for testing)."""
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict) -> AgentRegistry:
        agents = [AgentEntry.model_validate(a) for a in data["agents"]]
        phase_leads = data.get("phase_leads", {})
        return cls(agents, phase_leads)

    def get(self, name: str) -> AgentEntry | None:
        return self._by_name.get(name)

    def all_agents(self) -> list[AgentEntry]:
        return list(self._agents)

    def filter_by_mode(self, mode: str) -> list[AgentEntry]:
        return [a for a in self._agents if mode in a.orchestration_modes]

    def filter_by_phase(self, phase: str) -> list[AgentEntry]:
        return [a for a in self._agents if phase in a.phases]

    def filter_by_stack(
        self,
        stacks: set[str],
        *,
        enabled_phases: set[str] | None = None,
    ) -> list[AgentEntry]:
        result: list[AgentEntry] = []
        for agent in self._agents:
            if agent.optional and enabled_phases:
                agent_phases = set(agent.phases)
                if not (agent_phases & enabled_phases):
                    continue
            elif agent.optional:
                continue
            if agent.applicable_stacks is not None:
                if not stacks or not (set(agent.applicable_stacks) & stacks):
                    continue
            result.append(agent)
        return result

    def get_writers(self, mode: str | None = None) -> list[AgentEntry]:
        agents = self._agents if mode is None else self.filter_by_mode(mode)
        return [a for a in agents if a.can_write]

    def get_for_task_type(self, task_type: str) -> list[AgentEntry]:
        return [a for a in self._agents if task_type in a.task_types]

    def get_phase_roles(self, phase: str) -> list[str]:
        """Get agent names for a delivery phase (short names without 'delivery-' prefix)."""
        agents = self.filter_by_phase(phase)
        sworm_agents = [a for a in agents if "sworm" in a.orchestration_modes]
        result = []
        for a in sworm_agents:
            name = a.name
            if name.startswith("delivery-"):
                name = name[len("delivery-") :]
            result.append(name)
        return result

    def get_phase_lead(self, phase: str) -> str | None:
        lead = self._phase_leads.get(phase)
        if lead and lead.startswith("delivery-"):
            return lead[len("delivery-") :]
        return lead
