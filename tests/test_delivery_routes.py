"""Tests for server/routes_delivery.py — delivery HTTP API."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from stratus.orchestration.delivery_coordinator import DeliveryCoordinator
from stratus.orchestration.delivery_models import DeliveryPhase, DeliveryState
from stratus.server.app import create_app


@pytest.fixture
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    app = create_app(db_path=":memory:", learning_db_path=":memory:")
    with TestClient(app) as c:
        from stratus.orchestration.delivery_config import DeliveryConfig
        from stratus.orchestration.delivery_coordinator import DeliveryCoordinator

        session_dir = tmp_path / "sessions" / "test"
        session_dir.mkdir(parents=True)
        config = DeliveryConfig(enabled=True)
        coord = DeliveryCoordinator(session_dir=session_dir, config=config)
        app.state.delivery_coordinator = coord
        yield c


class TestGetDeliveryState:
    def test_returns_no_active_when_no_state(self, client: TestClient) -> None:
        resp = client.get("/api/delivery/state")
        assert resp.status_code == 200
        assert resp.json()["active"] is False

    def test_returns_state_after_start(self, client: TestClient) -> None:
        _ = client.post(
            "/api/delivery/start",
            json={"slug": "my-feat", "mode": "classic"},
        )
        resp = client.get("/api/delivery/state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is True
        assert "delivery_phase" in data
        assert data["slug"] == "my-feat"


class TestStartDelivery:
    def test_start_returns_state(self, client: TestClient) -> None:
        resp = client.post(
            "/api/delivery/start",
            json={"slug": "feat-x", "mode": "classic"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "feat-x"
        assert "delivery_phase" in data

    def test_start_missing_slug_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/delivery/start", json={"mode": "classic"})
        assert resp.status_code == 422

    def test_start_with_plan_path(self, client: TestClient) -> None:
        resp = client.post(
            "/api/delivery/start",
            json={"slug": "feat", "mode": "classic", "plan_path": "/plan.md"},
        )
        assert resp.status_code == 200

    def test_start_invalid_json_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/delivery/start",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    def test_start_duplicate_returns_409(self, client: TestClient) -> None:
        _ = client.post("/api/delivery/start", json={"slug": "feat", "mode": "classic"})
        resp = client.post("/api/delivery/start", json={"slug": "feat2", "mode": "classic"})
        assert resp.status_code == 409


class TestAdvanceDelivery:
    def test_advance_moves_to_next_phase(self, client: TestClient) -> None:
        _ = client.post("/api/delivery/start", json={"slug": "feat", "mode": "classic"})
        first_phase: str = client.get("/api/delivery/state").json()["delivery_phase"]

        resp = client.post("/api/delivery/advance")
        assert resp.status_code == 200
        assert resp.json()["delivery_phase"] != first_phase

    def test_advance_no_active_returns_409(self, client: TestClient) -> None:
        resp = client.post("/api/delivery/advance")
        assert resp.status_code == 409


class TestSkipDelivery:
    def test_skip_advances_past_current_phase(self, client: TestClient) -> None:
        _ = client.post("/api/delivery/start", json={"slug": "feat", "mode": "classic"})
        resp = client.post("/api/delivery/skip", json={"reason": "Not needed"})
        assert resp.status_code == 200
        assert "delivery_phase" in resp.json()

    def test_skip_missing_reason_returns_422(self, client: TestClient) -> None:
        _ = client.post("/api/delivery/start", json={"slug": "feat", "mode": "classic"})
        resp = client.post("/api/delivery/skip", json={})
        assert resp.status_code == 422

    def test_skip_no_active_returns_409(self, client: TestClient) -> None:
        resp = client.post("/api/delivery/skip", json={"reason": "skip"})
        assert resp.status_code == 409


class TestFixLoop:
    def test_fix_loop_from_qa_returns_implementation(self, client: TestClient) -> None:
        coord = app_state_delivery_coordinator(client)
        coord._state = DeliveryState(
            delivery_phase=DeliveryPhase.QA,
            slug="feat",
            orchestration_mode="classic",
        )
        resp = client.post("/api/delivery/fix-loop")
        assert resp.status_code == 200
        assert resp.json()["delivery_phase"] == "implementation"

    def test_fix_loop_from_implementation_returns_409(self, client: TestClient) -> None:
        _ = client.post("/api/delivery/start", json={"slug": "feat", "mode": "classic"})
        # IMPLEMENTATION phase cannot start a fix loop
        resp = client.post("/api/delivery/fix-loop")
        assert resp.status_code == 409

    def test_fix_loop_no_active_returns_409(self, client: TestClient) -> None:
        resp = client.post("/api/delivery/fix-loop")
        assert resp.status_code == 409


class TestCompleteDelivery:
    def test_complete_from_learning_succeeds(self, client: TestClient) -> None:
        coord = app_state_delivery_coordinator(client)
        coord._state = DeliveryState(
            delivery_phase=DeliveryPhase.LEARNING,
            slug="feat",
            orchestration_mode="classic",
        )
        resp = client.post("/api/delivery/complete")
        assert resp.status_code == 200

    def test_complete_from_wrong_phase_returns_409(self, client: TestClient) -> None:
        _ = client.post("/api/delivery/start", json={"slug": "feat", "mode": "classic"})
        resp = client.post("/api/delivery/complete")
        assert resp.status_code == 409

    def test_complete_no_active_returns_409(self, client: TestClient) -> None:
        resp = client.post("/api/delivery/complete")
        assert resp.status_code == 409


class TestGetRoles:
    def test_get_roles_no_active_returns_empty(self, client: TestClient) -> None:
        resp = client.get("/api/delivery/roles")
        assert resp.status_code == 200
        data = resp.json()
        assert data["roles"] == []
        assert data["phase_lead"] is None

    def test_get_roles_returns_phase_roles(self, client: TestClient) -> None:
        _ = client.post("/api/delivery/start", json={"slug": "feat", "mode": "classic"})
        resp = client.get("/api/delivery/roles")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["roles"], list)
        assert len(data["roles"]) > 0


class TestGetDispatch:
    def test_dispatch_not_enabled_returns_503(self, client: TestClient) -> None:
        # Remove coordinator to simulate disabled
        from starlette.applications import Starlette

        assert isinstance(client.app, Starlette)
        client.app.state.delivery_coordinator = None
        resp = client.get("/api/delivery/dispatch")
        assert resp.status_code == 503

    def test_dispatch_no_active_returns_inactive(self, client: TestClient) -> None:
        resp = client.get("/api/delivery/dispatch")
        assert resp.status_code == 200
        assert resp.json()["active"] is False

    def test_dispatch_returns_context_after_start(self, client: TestClient) -> None:
        _ = client.post(
            "/api/delivery/start",
            json={"slug": "feat", "mode": "classic"},
        )
        resp = client.get("/api/delivery/dispatch")
        assert resp.status_code == 200
        data = resp.json()
        assert "phase" in data
        assert "agents" in data
        assert "objectives" in data
        assert "briefing_markdown" in data

    def test_dispatch_agents_have_delivery_prefix(self, client: TestClient) -> None:
        _ = client.post(
            "/api/delivery/start",
            json={"slug": "feat", "mode": "classic"},
        )
        data = client.get("/api/delivery/dispatch").json()
        for agent in data["agents"]:
            assert agent["agent_name"].startswith("delivery-")


class TestPostDispatchAssignments:
    def test_assignments_not_enabled_returns_503(self, client: TestClient) -> None:
        from starlette.applications import Starlette

        assert isinstance(client.app, Starlette)
        client.app.state.delivery_coordinator = None
        resp = client.post(
            "/api/delivery/dispatch/assignments",
            json={"tasks": []},
        )
        assert resp.status_code == 503

    def test_assignments_no_active_returns_inactive(self, client: TestClient) -> None:
        resp = client.post(
            "/api/delivery/dispatch/assignments",
            json={"tasks": []},
        )
        assert resp.status_code == 200
        assert resp.json()["active"] is False

    def test_assignments_returns_markdown(self, client: TestClient) -> None:
        _ = client.post(
            "/api/delivery/start",
            json={"slug": "feat", "mode": "classic"},
        )
        resp = client.post(
            "/api/delivery/dispatch/assignments",
            json={
                "tasks": [
                    {"id": "T-1", "description": "Add API endpoint"},
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "assignments" in data
        assert "T-1" in data["assignments"]

    def test_assignments_invalid_json_returns_422(self, client: TestClient) -> None:
        _ = client.post(
            "/api/delivery/start",
            json={"slug": "feat", "mode": "classic"},
        )
        resp = client.post(
            "/api/delivery/dispatch/assignments",
            content=b"bad",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422


def app_state_delivery_coordinator(
    client: TestClient,
) -> DeliveryCoordinator:
    """Helper to access the delivery coordinator from app state."""
    from starlette.applications import Starlette

    from stratus.orchestration.delivery_coordinator import (
        DeliveryCoordinator,
    )

    assert isinstance(client.app, Starlette)
    coord = client.app.state.delivery_coordinator
    assert isinstance(coord, DeliveryCoordinator)
    return coord
