"""Deterministic task routing using the agent registry."""

from __future__ import annotations

from pydantic import BaseModel

from stratus.registry.loader import AgentRegistry


class RoutingEntry(BaseModel):
    """Explicit routing rule for overlapping agent pairs."""

    task_type: str
    default_agent: str
    sworm_agent: str


class RoutingError(Exception):
    """Raised when no agent can be found for a task."""


# Explicit routing table for the 4 overlapping pairs
ROUTING_TABLE: list[RoutingEntry] = [
    RoutingEntry(
        task_type="test",
        default_agent="qa-engineer",
        sworm_agent="delivery-qa-engineer",
    ),
    RoutingEntry(
        task_type="architecture",
        default_agent="architecture-guide",
        sworm_agent="delivery-strategic-architect",
    ),
    RoutingEntry(
        task_type="implementation",
        default_agent="framework-expert",
        sworm_agent="delivery-backend-engineer",
    ),
    RoutingEntry(
        task_type="review",
        default_agent="spec-reviewer-quality",
        sworm_agent="delivery-code-reviewer",
    ),
]

_ROUTING_INDEX: dict[str, RoutingEntry] = {e.task_type: e for e in ROUTING_TABLE}


def route_task(
    task_type: str,
    mode: str,
    available_agents: list[str] | None = None,
    *,
    require_write: bool = False,
) -> str:
    """Deterministic routing. Raises RoutingError if no agent found.

    Args:
        task_type: The type of task (e.g., "implementation", "test", "review")
        mode: "default" or "sworm"
        available_agents: Optional whitelist of agent names
        require_write: If True, only route to agents with can_write=True
    """
    registry = AgentRegistry.load()

    # Check explicit routing table first
    entry = _ROUTING_INDEX.get(task_type)
    if entry:
        agent_name = entry.default_agent if mode == "default" else entry.sworm_agent
        if available_agents is None or agent_name in available_agents:
            if require_write:
                agent = registry.get(agent_name)
                if agent and agent.can_write:
                    return agent_name
            else:
                return agent_name

    # Fall back to registry lookup by task_type
    candidates = registry.get_for_task_type(task_type)

    # Filter by mode
    candidates = [a for a in candidates if mode in a.orchestration_modes]

    # Filter by availability
    if available_agents is not None:
        candidates = [a for a in candidates if a.name in available_agents]

    # Filter by write capability
    if require_write:
        candidates = [a for a in candidates if a.can_write]

    if not candidates:
        raise RoutingError(
            f"No agent found for task_type='{task_type}', mode='{mode}'"
            + (", require_write=True" if require_write else "")
        )

    return candidates[0].name
