"""Tests for server/routes_dashboard.py — dashboard aggregated endpoint + static serving."""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from stratus.server.app import create_app


@pytest.fixture
def client(tmp_path: Path):
    app = create_app(db_path=":memory:", learning_db_path=":memory:")
    with TestClient(app) as c:
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


class TestDashboardState:
    def test_dashboard_state_returns_all_sections(self, client: TestClient):
        resp = client.get("/api/dashboard/state")
        assert resp.status_code == 200
        data = resp.json()
        assert "orchestration" in data
        assert "agents" in data
        assert "learning" in data
        assert "memory" in data
        assert "version" in data
        assert "timestamp" in data

    def test_dashboard_state_inactive_orchestration(self, client: TestClient):
        resp = client.get("/api/dashboard/state")
        data = resp.json()
        orch = data["orchestration"]
        assert orch["mode"] == "inactive"
        assert orch["spec"] is None
        assert orch["delivery"] is None

    def test_dashboard_state_with_active_spec(self, client: TestClient):
        client.post("/api/orchestration/start", json={"slug": "dash-feat"})
        resp = client.get("/api/dashboard/state")
        data = resp.json()
        orch = data["orchestration"]
        assert orch["mode"] == "spec"
        assert orch["spec"]["phase"] == "plan"
        assert orch["spec"]["slug"] == "dash-feat"

    def test_dashboard_state_agents_change_with_phase(self, client: TestClient):
        client.post("/api/orchestration/start", json={"slug": "dash-feat"})

        # Plan phase agents
        resp = client.get("/api/dashboard/state")
        plan_agents = resp.json()["agents"]
        plan_labels = {a["label"] for a in plan_agents}
        assert "architecture-guide" in plan_labels
        assert "plan-verifier" in plan_labels

        # Advance to implement
        client.post("/api/orchestration/approve-plan", json={"total_tasks": 3})
        resp = client.get("/api/dashboard/state")
        impl_agents = resp.json()["agents"]
        impl_labels = {a["label"] for a in impl_agents}
        assert "framework-expert" in impl_labels

    def test_dashboard_state_memory_section(self, client: TestClient):
        resp = client.get("/api/dashboard/state")
        data = resp.json()
        mem = data["memory"]
        assert "total_events" in mem
        assert "total_sessions" in mem

    def test_dashboard_state_learning_section(self, client: TestClient):
        resp = client.get("/api/dashboard/state")
        data = resp.json()
        learn = data["learning"]
        assert "enabled" in learn
        assert "sensitivity" in learn
        assert "proposals" in learn
        assert "stats" in learn

    def test_dashboard_state_team_section(self, client: TestClient):
        resp = client.get("/api/dashboard/state")
        data = resp.json()
        team = data["orchestration"]["team"]
        assert "enabled" in team
        assert "mode" in team


class TestDashboardRegistry:
    def test_registry_returns_agents(self, client: TestClient):
        resp = client.get("/api/dashboard/registry")
        assert resp.status_code == 200
        data = resp.json()
        assert "agents" in data
        assert isinstance(data["agents"], list)
        assert len(data["agents"]) > 0
        assert "name" in data["agents"][0]

    def test_registry_returns_skills_and_rules(self, client: TestClient):
        resp = client.get("/api/dashboard/registry")
        data = resp.json()
        assert "skills" in data
        assert "rules" in data
        assert isinstance(data["skills"], list)
        assert isinstance(data["rules"], list)

    def test_registry_agents_have_expected_fields(self, client: TestClient):
        resp = client.get("/api/dashboard/registry")
        agent = resp.json()["agents"][0]
        assert "name" in agent
        assert "model" in agent
        assert "layer" in agent
        assert "phases" in agent
        assert "can_write" in agent


class TestDashboardPage:
    def test_dashboard_page_returns_html(self, client: TestClient):
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "<canvas" in resp.text

    def test_static_css_served(self, client: TestClient):
        resp = client.get("/dashboard/static/dashboard.css")
        assert resp.status_code == 200
        assert "text/css" in resp.headers["content-type"]

    def test_static_js_served(self, client: TestClient):
        resp = client.get("/dashboard/static/dashboard.js")
        assert resp.status_code == 200
        assert "javascript" in resp.headers["content-type"]
