"""Deterministic task routing using the agent registry."""

from __future__ import annotations

from pathlib import Path

from stratus.registry.loader import AgentRegistry


class RoutingError(Exception):
    """Raised when no agent can be found for a task."""


_ROUTING_PRIORITY: dict[str, str] = {
    "test": "delivery-qa-engineer",
    "architecture": "delivery-strategic-architect",
    "implementation": "delivery-backend-engineer",
    "review": "delivery-code-reviewer",
}


def route_task(
    task_type: str,
    available_agents: list[str] | None = None,
    *,
    require_write: bool = False,
    prefer_delivery: bool = True,
    registry: AgentRegistry | None = None,
    project_root: Path | None = None,
) -> str:
    """Deterministic routing. Raises RoutingError if no agent found.

    Args:
        task_type: The type of task (e.g., "implementation", "test", "review")
        available_agents: Optional whitelist of agent names
        require_write: If True, only route to agents with can_write=True
        prefer_delivery: If True, prefer delivery agents for overlapping task types
        registry: Optional pre-loaded registry. If None, loads automatically.
        project_root: Optional project root for user agent discovery. Merged with bundled.
    """
    if registry is None:
        if project_root is not None:
            registry = AgentRegistry.load_merged(project_root)
        else:
            registry = AgentRegistry.load()

    if prefer_delivery and task_type in _ROUTING_PRIORITY:
        preferred = _ROUTING_PRIORITY[task_type]
        if available_agents is None or preferred in available_agents:
            agent = registry.get(preferred)
            if agent:
                if require_write and not agent.can_write:
                    pass
                else:
                    return preferred

    candidates = registry.get_for_task_type(task_type)

    if available_agents is not None:
        candidates = [a for a in candidates if a.name in available_agents]

    if require_write:
        candidates = [a for a in candidates if a.can_write]

    if not candidates:
        raise RoutingError(
            f"No agent found for task_type='{task_type}'"
            + (", require_write=True" if require_write else "")
        )

    return candidates[0].name
