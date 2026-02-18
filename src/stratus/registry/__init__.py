"""Unified agent registry: single source of truth for all agent metadata."""

from stratus.registry.loader import AgentRegistry
from stratus.registry.models import AgentEntry
from stratus.registry.routing import ROUTING_TABLE, RoutingEntry, RoutingError, route_task
from stratus.registry.validation import (
    ValidationWarning,
    validate_mode_agents,
    validate_team_composition,
    validate_write_permissions,
)

__all__ = [
    "AgentEntry",
    "AgentRegistry",
    "ROUTING_TABLE",
    "RoutingEntry",
    "RoutingError",
    "ValidationWarning",
    "route_task",
    "validate_mode_agents",
    "validate_team_composition",
    "validate_write_permissions",
]
