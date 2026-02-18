"""Team composition and mode validation using the agent registry."""

from __future__ import annotations

from stratus.registry.loader import AgentRegistry


class ValidationWarning:
    """A non-fatal validation finding."""

    def __init__(self, message: str) -> None:
        self.message = message

    def __repr__(self) -> str:
        return f"ValidationWarning({self.message!r})"


def validate_team_composition(
    agent_names: list[str],
    phase: str,
    registry: AgentRegistry | None = None,
) -> list[ValidationWarning]:
    """Validate that all agents exist and match the given phase."""
    if registry is None:
        registry = AgentRegistry.load()

    warnings: list[ValidationWarning] = []

    for name in agent_names:
        entry = registry.get(name)
        if entry is None:
            warnings.append(ValidationWarning(f"Agent '{name}' not found in registry"))
            continue
        if phase not in entry.phases:
            warnings.append(
                ValidationWarning(
                    f"Agent '{name}' is not assigned to phase '{phase}' "
                    f"(assigned: {entry.phases})"
                )
            )

    return warnings


def validate_mode_agents(
    mode: str,
    registry: AgentRegistry | None = None,
) -> list[ValidationWarning]:
    """Validate that a mode has agents available."""
    if registry is None:
        registry = AgentRegistry.load()

    agents = registry.filter_by_mode(mode)
    warnings: list[ValidationWarning] = []

    if not agents:
        warnings.append(ValidationWarning(f"No agents found for mode '{mode}'"))

    return warnings


def validate_write_permissions(
    agent_names: list[str],
    phase: str,
    registry: AgentRegistry | None = None,
) -> list[ValidationWarning]:
    """Flag agents with write permissions in review/verify phases."""
    if registry is None:
        registry = AgentRegistry.load()

    review_phases = {"verify", "qa", "governance"}
    if phase not in review_phases:
        return []

    warnings: list[ValidationWarning] = []
    for name in agent_names:
        entry = registry.get(name)
        if entry and entry.can_write:
            warnings.append(
                ValidationWarning(
                    f"Agent '{name}' has write permissions but is assigned "
                    f"to review phase '{phase}'"
                )
            )

    return warnings
