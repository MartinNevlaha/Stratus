"""AgentRegistry: load and query the unified agent registry."""

from __future__ import annotations

import json
import re
from importlib import resources
from pathlib import Path

from stratus.registry.models import AgentEntry


def parse_agent_frontmatter(md_path: Path) -> AgentEntry | None:
    """Parse agent metadata from .md file frontmatter.

    Returns None if parsing fails or required fields are missing.
    """
    try:
        content = md_path.read_text(encoding="utf-8")
    except OSError:
        return None

    if not content.startswith("---"):
        return None

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None

    frontmatter = parts[1].strip()
    fm: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip().strip('"').strip("'")

    name = fm.get("name") or md_path.stem
    if not name:
        return None

    tools_raw = fm.get("tools", "")
    can_write = any(t in tools_raw for t in ("Write", "Edit", "NotebookEdit"))

    model = fm.get("model", "sonnet").lower()
    if model not in ("sonnet", "opus", "haiku"):
        model = "sonnet"

    description = fm.get("description", "")

    layer = "user"
    if any(kw in description.lower() for kw in ("process", "planning", "coordination")):
        layer = "process"
    elif any(kw in description.lower() for kw in ("engineer", "implement", "backend", "frontend")):
        layer = "engineering"

    phases: list[str] = []
    if any(kw in description.lower() for kw in ("implement", "build", "code")):
        phases.append("implementation")
    if any(kw in description.lower() for kw in ("test", "qa", "verify")):
        phases.append("verify")
    if any(kw in description.lower() for kw in ("review", "compliance")):
        phases.append("verify")
    if any(kw in description.lower() for kw in ("architecture", "design", "system")):
        phases.append("plan")
    if not phases:
        phases = ["implementation"]

    task_types: list[str] = []
    if any(kw in description.lower() for kw in ("implement", "build", "feature")):
        task_types.append("implementation")
    if any(kw in description.lower() for kw in ("test", "qa")):
        task_types.append("test")
    if any(kw in description.lower() for kw in ("review", "compliance")):
        task_types.append("review")
    if any(kw in description.lower() for kw in ("architecture", "design")):
        task_types.append("architecture")
    if not task_types:
        task_types = ["implementation"]

    keywords: list[str] = []
    keyword_pattern = re.compile(
        r"\b(implement|build|test|review|architecture|design|api|ui|frontend|backend|database|security|performance|docs)\b",
        re.IGNORECASE,
    )
    for match in keyword_pattern.finditer(description.lower()):
        kw = match.group(1).lower()
        if kw not in keywords:
            keywords.append(kw)

    return AgentEntry(
        name=name,
        filename=md_path.name,
        model=model,
        can_write=can_write,
        layer=layer,
        phases=phases,
        task_types=task_types,
        applicable_stacks=None,
        orchestration_modes=["default"],
        optional=False,
        keywords=keywords,
    )


def discover_user_agents(project_root: Path) -> list[AgentEntry]:
    """Scan .claude/agents/ for user-defined agents.

    Returns list of AgentEntry objects parsed from .md files.
    Files with managed header (framework-owned) are excluded.
    """
    agents_dir = project_root / ".claude" / "agents"
    if not agents_dir.exists():
        return []

    entries: list[AgentEntry] = []
    for md_file in sorted(agents_dir.glob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
            if content.startswith("<!-- STRATUS-MANAGED:"):
                continue
        except OSError:
            continue

        entry = parse_agent_frontmatter(md_file)
        if entry:
            entries.append(entry)

    return entries


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
    def load_merged(cls, project_root: Path | None = None) -> AgentRegistry:
        """Load bundled registry merged with user-defined agents.

        User agents with same name as bundled agent override the bundled entry.
        New user agents are appended to the registry.

        Args:
            project_root: Project root directory. If None, returns bundled only.
        """
        bundled = cls.load()
        if project_root is None:
            return bundled

        user_agents = discover_user_agents(project_root)
        if not user_agents:
            return bundled

        merged_agents: list[AgentEntry] = list(bundled._agents)
        merged_by_name: dict[str, AgentEntry] = dict(bundled._by_name)

        for user_agent in user_agents:
            if user_agent.name in merged_by_name:
                idx = next(
                    (i for i, a in enumerate(merged_agents) if a.name == user_agent.name), None
                )
                if idx is not None:
                    merged_agents[idx] = user_agent
                    merged_by_name[user_agent.name] = user_agent
            else:
                merged_agents.append(user_agent)
                merged_by_name[user_agent.name] = user_agent

        return cls(merged_agents, dict(bundled._phase_leads))

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
        """Get agent names for a phase (short names without 'delivery-' prefix)."""
        agents = self.filter_by_phase(phase)
        default_agents = [a for a in agents if "default" in a.orchestration_modes]
        result = []
        for a in default_agents:
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
