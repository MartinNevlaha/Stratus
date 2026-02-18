"""Tests for deterministic task routing via the agent registry."""

from __future__ import annotations

import pytest

from stratus.registry.routing import (
    ROUTING_TABLE,
    RoutingError,
    route_task,
)


@pytest.mark.unit
def test_route_implementation_default():
    assert route_task("implementation", "default") == "framework-expert"


@pytest.mark.unit
def test_route_implementation_swords():
    assert route_task("implementation", "swords") == "delivery-backend-engineer"


@pytest.mark.unit
def test_route_test_default():
    assert route_task("test", "default") == "qa-engineer"


@pytest.mark.unit
def test_route_test_swords():
    assert route_task("test", "swords") == "delivery-qa-engineer"


@pytest.mark.unit
def test_route_architecture_default():
    assert route_task("architecture", "default") == "architecture-guide"


@pytest.mark.unit
def test_route_review_default():
    assert route_task("review", "default") == "spec-reviewer-quality"


@pytest.mark.unit
def test_route_review_swords():
    assert route_task("review", "swords") == "delivery-code-reviewer"


@pytest.mark.unit
def test_route_unknown_type_raises():
    with pytest.raises(RoutingError):
        route_task("nonexistent-task-type", "default")


@pytest.mark.unit
def test_route_with_available_agents_filter():
    # Provide whitelist that excludes the table-primary agent; falls back to registry
    # "qa-engineer" excluded → should raise (no other default agent covers "test")
    with pytest.raises(RoutingError):
        route_task("test", "default", available_agents=["framework-expert"])


@pytest.mark.unit
def test_route_require_write_filters():
    # "architecture-guide" cannot write; delivery-strategic-architect also cannot write.
    # With require_write=True, routing table still selects the agent name from the table,
    # but then fails the can_write check and falls to registry fallback which also yields
    # no writers -> RoutingError.
    with pytest.raises(RoutingError):
        route_task("architecture", "default", require_write=True)


@pytest.mark.unit
def test_route_require_write_no_candidate():
    # "review" default -> spec-reviewer-quality (can_write=False); no other writer exists
    with pytest.raises(RoutingError):
        route_task("review", "default", require_write=True)


@pytest.mark.unit
def test_routing_table_has_four_entries():
    assert len(ROUTING_TABLE) == 4


@pytest.mark.unit
def test_route_never_returns_unassigned():
    for entry in ROUTING_TABLE:
        result_default = route_task(entry.task_type, "default")
        result_swords = route_task(entry.task_type, "swords")
        assert "_unassigned_" not in result_default
        assert "_unassigned_" not in result_swords
