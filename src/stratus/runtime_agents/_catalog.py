"""Catalog of runtime agent and skill specs with filtering logic."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources

from stratus.bootstrap.models import ServiceType


@dataclass(frozen=True)
class AgentSpec:
    filename: str
    applicable_stacks: frozenset[ServiceType] | None
    layer: str
    optional: bool = False


@dataclass(frozen=True)
class SkillSpec:
    dirname: str
    agent_filename: str
    phase: str
    optional: bool = False


def _entry_to_spec(entry: object) -> AgentSpec:
    """Convert a registry AgentEntry to an AgentSpec."""
    stacks: frozenset[ServiceType] | None = None
    if entry.applicable_stacks is not None:  # type: ignore[union-attr]
        stacks = frozenset(
            ServiceType(s) for s in entry.applicable_stacks  # type: ignore[union-attr]
        )
    return AgentSpec(
        filename=entry.filename,  # type: ignore[union-attr]
        applicable_stacks=stacks,
        layer=entry.layer,  # type: ignore[union-attr]
        optional=entry.optional,  # type: ignore[union-attr]
    )


def _build_catalog() -> list[AgentSpec]:
    """Build AGENT_CATALOG from the unified agent registry."""
    from stratus.registry.loader import AgentRegistry

    registry = AgentRegistry.load()
    return [_entry_to_spec(e) for e in registry.filter_by_mode("swords")]


AGENT_CATALOG: list[AgentSpec] = _build_catalog()

SKILL_CATALOG: list[SkillSpec] = [
    SkillSpec("run-discovery", "delivery-product-owner.md", "discovery", optional=True),
    SkillSpec(
        "create-architecture", "delivery-strategic-architect.md", "architecture", optional=True
    ),
    SkillSpec("plan-sprint", "delivery-tpm.md", "planning"),
    SkillSpec("security-review", "delivery-security-reviewer.md", "governance"),
    SkillSpec(
        "performance-benchmark", "delivery-performance-engineer.md", "performance", optional=True
    ),
    SkillSpec("release-prepare", "delivery-release-manager.md", "release"),
    SkillSpec("governance-audit", "delivery-risk-officer.md", "governance"),
]

def get_detected_types(graph: dict[str, list[dict[str, str]]] | None) -> set[ServiceType]:
    """Extract detected ServiceType values from a ProjectGraph dict."""
    if not graph:
        return set()
    types: set[ServiceType] = set()
    for svc in graph.get("services", []):
        svc_type = svc.get("type", "")
        try:
            types.add(ServiceType(svc_type))
        except ValueError:
            continue
    return types


def filter_agents(
    detected_types: set[ServiceType],
    *,
    enabled_phases: set[str] | None = None,
) -> list[AgentSpec]:
    """Filter AGENT_CATALOG by stack detection and phase configuration."""
    from stratus.registry.loader import AgentRegistry

    stacks = {t.value for t in detected_types}
    registry = AgentRegistry.load()
    entries = registry.filter_by_stack(stacks, enabled_phases=enabled_phases)
    swords = [e for e in entries if "swords" in e.orchestration_modes]
    return [_entry_to_spec(e) for e in swords]


def filter_skills(
    *,
    enabled_phases: set[str] | None = None,
) -> list[SkillSpec]:
    """Filter SKILL_CATALOG by phase configuration."""
    result: list[SkillSpec] = []
    for spec in SKILL_CATALOG:
        if spec.optional and (not enabled_phases or spec.phase not in enabled_phases):
            continue
        result.append(spec)
    return result


def read_agent_template(filename: str) -> str:
    """Read an agent .md template from package data."""
    agents_pkg = resources.files("stratus.runtime_agents.agents")
    resource = agents_pkg.joinpath(filename)
    return resource.read_text(encoding="utf-8")


def read_skill_template(dirname: str) -> str:
    """Read a skill SKILL.md template from package data."""
    skills_pkg = resources.files("stratus.runtime_agents.skills")
    resource = skills_pkg.joinpath(dirname).joinpath("SKILL.md")
    return resource.read_text(encoding="utf-8")
