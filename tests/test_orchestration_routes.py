"""Tests for server/routes_orchestration.py — orchestration HTTP API."""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from stratus.server.app import create_app


@pytest.fixture
def client(tmp_path: Path):
    app = create_app(db_path=":memory:", learning_db_path=":memory:")
    with TestClient(app) as c:
        # Override coordinator AFTER lifespan runs (TestClient triggers it)
        from stratus.orchestration.coordinator import SpecCoordinator
        from stratus.orchestration.models import TeamConfig

        session_dir = tmp_path / "sessions" / "test"
        session_dir.mkdir(parents=True)
        app.state.coordinator = SpecCoordinator(
            session_dir=session_dir,
            project_root=tmp_path,
            api_url="http://127.0.0.1:41777",
        )
        app.state.team_config = TeamConfig()
        yield c


class TestOrchestrationState:
    def test_get_state_no_active_spec(self, client: TestClient):
        resp = client.get("/api/orchestration/state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is False

    def test_get_state_with_active_spec(self, client: TestClient):
        # Start a spec via POST
        resp = client.post(
            "/api/orchestration/start",
            json={"slug": "my-feat", "plan_path": "/plan.md"},
        )
        assert resp.status_code == 200

        resp = client.get("/api/orchestration/state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is True
        assert data["phase"] == "plan"
        assert data["slug"] == "my-feat"


class TestStartSpec:
    def test_start_spec(self, client: TestClient):
        resp = client.post(
            "/api/orchestration/start",
            json={"slug": "my-feat"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "my-feat"
        assert data["phase"] == "plan"

    def test_start_spec_duplicate(self, client: TestClient):
        client.post("/api/orchestration/start", json={"slug": "feat"})
        resp = client.post("/api/orchestration/start", json={"slug": "feat2"})
        assert resp.status_code == 409

    def test_start_spec_missing_slug(self, client: TestClient):
        resp = client.post("/api/orchestration/start", json={})
        assert resp.status_code == 422


class TestApprovePlan:
    def test_approve_plan(self, client: TestClient):
        client.post("/api/orchestration/start", json={"slug": "feat"})
        resp = client.post(
            "/api/orchestration/approve-plan",
            json={"total_tasks": 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "implement"
        assert data["total_tasks"] == 3

    def test_approve_plan_no_spec(self, client: TestClient):
        resp = client.post(
            "/api/orchestration/approve-plan",
            json={"total_tasks": 3},
        )
        assert resp.status_code == 409


class TestVerdicts:
    def test_get_verdicts_empty(self, client: TestClient):
        resp = client.get("/api/orchestration/verdicts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["verdicts"] == []


class TestTeamEndpoint:
    def test_get_team_no_teams(self, client: TestClient):
        resp = client.get("/api/orchestration/team")
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False

    def test_get_team_backend_info(self, client: TestClient):
        resp = client.get("/api/orchestration/team")
        data = resp.json()
        assert data["mode"] == "task-tool"
