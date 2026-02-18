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


AGENT_CATALOG: list[AgentSpec] = [
    # Process layer — universal (all stacks)
    AgentSpec("delivery-product-owner.md", None, "process", optional=True),
    AgentSpec("delivery-tpm.md", None, "process"),
    AgentSpec("delivery-strategic-architect.md", None, "process", optional=True),
    AgentSpec("delivery-risk-officer.md", None, "process"),
    AgentSpec("delivery-security-reviewer.md", None, "process"),
    AgentSpec("delivery-quality-gate-manager.md", None, "process"),
    AgentSpec("delivery-release-manager.md", None, "process"),
    AgentSpec("delivery-cost-controller.md", None, "process"),
    # Engineering layer — stack-filtered
    AgentSpec("delivery-system-architect.md", None, "engineering", optional=True),
    AgentSpec(
        "delivery-backend-engineer.md",
        frozenset({ServiceType.NESTJS, ServiceType.PYTHON, ServiceType.GO, ServiceType.RUST}),
        "engineering",
    ),
    AgentSpec(
        "delivery-frontend-engineer.md",
        frozenset({ServiceType.NEXTJS, ServiceType.REACT_NATIVE}),
        "engineering",
    ),
    AgentSpec(
        "delivery-mobile-engineer.md",
        frozenset({ServiceType.REACT_NATIVE}),
        "engineering",
    ),
    AgentSpec("delivery-devops-engineer.md", None, "engineering"),
    AgentSpec("delivery-database-engineer.md", None, "engineering"),
    AgentSpec("delivery-qa-engineer.md", None, "engineering"),
    AgentSpec("delivery-debugger.md", None, "engineering"),
    AgentSpec("delivery-performance-engineer.md", None, "engineering", optional=True),
    AgentSpec("delivery-code-reviewer.md", None, "engineering"),
    AgentSpec("delivery-documentation-engineer.md", None, "engineering"),
]

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

# Maps optional agent filenames to their associated phase name.
_OPTIONAL_AGENT_PHASES: dict[str, str] = {
    "delivery-product-owner.md": "discovery",
    "delivery-strategic-architect.md": "architecture",
    "delivery-system-architect.md": "architecture",
    "delivery-performance-engineer.md": "performance",
}


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
    result: list[AgentSpec] = []
    for spec in AGENT_CATALOG:
        if spec.optional:
            phase = _OPTIONAL_AGENT_PHASES.get(spec.filename)
            if not enabled_phases or phase not in enabled_phases:
                continue
        if spec.applicable_stacks is not None:
            if not detected_types or not (spec.applicable_stacks & detected_types):
                continue
        result.append(spec)
    return result


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
