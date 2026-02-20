"""Tests for deterministic task routing via the agent registry."""

from __future__ import annotations

import pytest

from stratus.registry.routing import RoutingError, route_task


@pytest.mark.unit
def test_route_implementation_prefers_delivery():
    assert route_task("implementation") == "delivery-backend-engineer"


@pytest.mark.unit
def test_route_test_prefers_delivery():
    assert route_task("test") == "delivery-qa-engineer"


@pytest.mark.unit
def test_route_architecture_prefers_delivery():
    assert route_task("architecture") == "delivery-strategic-architect"


@pytest.mark.unit
def test_route_review_prefers_delivery():
    assert route_task("review") == "delivery-code-reviewer"


@pytest.mark.unit
def test_route_unknown_type_raises():
    with pytest.raises(RoutingError):
        route_task("nonexistent-task-type")


@pytest.mark.unit
def test_route_with_available_agents_filter():
    with pytest.raises(RoutingError):
        route_task("test", available_agents=["delivery-implementation-expert"])


@pytest.mark.unit
def test_route_require_write_filters():
    with pytest.raises(RoutingError):
        route_task("architecture", require_write=True)


@pytest.mark.unit
def test_route_require_write_no_candidate():
    with pytest.raises(RoutingError):
        route_task("review", require_write=True)


@pytest.mark.unit
def test_route_implementation_with_write():
    result = route_task("implementation", require_write=True)
    assert result == "delivery-backend-engineer"


@pytest.mark.unit
def test_route_test_with_write():
    result = route_task("test", require_write=True)
    assert result == "delivery-qa-engineer"


@pytest.mark.unit
def test_route_fallback_to_registry():
    result = route_task("bug-fix")
    assert result in ("delivery-backend-engineer", "delivery-implementation-expert")


@pytest.mark.unit
def test_route_prefer_delivery_false():
    result = route_task("test", prefer_delivery=False)
    assert result == "delivery-qa-engineer"
