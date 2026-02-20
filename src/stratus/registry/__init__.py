"""Unified agent registry: single source of truth for all agent metadata."""

from stratus.registry.loader import (
    AgentRegistry,
    discover_user_agents,
    parse_agent_frontmatter,
)
from stratus.registry.models import AgentEntry
from stratus.registry.routing import RoutingError, route_task
from stratus.registry.validation import (
    ValidationWarning,
    validate_mode_agents,
    validate_team_composition,
    validate_write_permissions,
)

__all__ = [
    "AgentEntry",
    "AgentRegistry",
    "RoutingError",
    "ValidationWarning",
    "discover_user_agents",
    "parse_agent_frontmatter",
    "route_task",
    "validate_mode_agents",
    "validate_team_composition",
    "validate_write_permissions",
]
