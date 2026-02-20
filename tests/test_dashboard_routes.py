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
        assert "delivery-architecture-guide" in plan_labels
        assert "delivery-plan-verifier" in plan_labels

        # Advance to implement
        client.post("/api/orchestration/approve-plan", json={"total_tasks": 3})
        resp = client.get("/api/dashboard/state")
        impl_agents = resp.json()["agents"]
        impl_labels = {a["label"] for a in impl_agents}
        assert "delivery-implementation-expert" in impl_labels

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


class TestParseSkillFrontmatter:
    def test_parses_all_fields(self):
        from stratus.server.routes_dashboard import _parse_skill_frontmatter

        content = (
            "---\nname: run-tests\ndescription: Run the test suite\n"
            "agent: delivery-qa-engineer\ncontext: fork\n---\nInstructions body here."
        )
        result = _parse_skill_frontmatter(content)
        assert result["name"] == "run-tests"
        assert result["description"] == "Run the test suite"
        assert result["agent"] == "delivery-qa-engineer"
        assert result["context"] == "fork"
        assert result["body"] == "Instructions body here."

    def test_no_frontmatter_returns_body(self):
        from stratus.server.routes_dashboard import _parse_skill_frontmatter

        content = "Just plain content with no frontmatter."
        result = _parse_skill_frontmatter(content)
        assert result == {"body": content}

    def test_incomplete_frontmatter_returns_body(self):
        from stratus.server.routes_dashboard import _parse_skill_frontmatter

        content = "---\nonly one delimiter"
        result = _parse_skill_frontmatter(content)
        assert result == {"body": content}

    def test_empty_frontmatter_values_ignored(self):
        from stratus.server.routes_dashboard import _parse_skill_frontmatter

        content = "---\ndescription: My skill\nagent:\n---\nBody text."
        result = _parse_skill_frontmatter(content)
        assert result["description"] == "My skill"
        assert result["agent"] == ""
        assert result["body"] == "Body text."

    def test_colon_in_value_preserved(self):
        from stratus.server.routes_dashboard import _parse_skill_frontmatter

        content = "---\ndescription: Run tests: unit and integration\n---\nBody."
        result = _parse_skill_frontmatter(content)
        assert result["description"] == "Run tests: unit and integration"


class TestRegistrySkillsFrontmatter:
    def test_skill_with_skill_md_includes_parsed_fields(
        self, client: TestClient, tmp_path: Path, monkeypatch
    ):

        skills_dir = tmp_path / ".claude" / "skills" / "run-tests"
        skills_dir.mkdir(parents=True)
        skill_md = skills_dir / "SKILL.md"
        skill_md.write_text(
            "---\nname: run-tests\ndescription: Runs the project test suite\n"
            "agent: delivery-qa-engineer\ncontext: fork\n---\nRun all tests.\n"
        )
        monkeypatch.chdir(tmp_path)

        resp = client.get("/api/dashboard/registry")
        assert resp.status_code == 200
        skills = resp.json()["skills"]
        assert len(skills) == 1
        skill = skills[0]
        assert skill["name"] == "run-tests"
        assert skill["description"] == "Runs the project test suite"
        assert skill["agent"] == "delivery-qa-engineer"
        assert skill["context"] == "fork"
        assert "body" in skill

    def test_skill_without_skill_md_returns_name_and_path(
        self, client: TestClient, tmp_path: Path, monkeypatch
    ):

        skills_dir = tmp_path / ".claude" / "skills" / "my-skill"
        skills_dir.mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        resp = client.get("/api/dashboard/registry")
        skills = resp.json()["skills"]
        assert len(skills) == 1
        assert skills[0]["name"] == "my-skill"
        assert "description" not in skills[0]

    def test_skill_with_malformed_skill_md_still_returns_entry(
        self, client: TestClient, tmp_path: Path, monkeypatch
    ):
        skills_dir = tmp_path / ".claude" / "skills" / "broken-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("not frontmatter at all")
        monkeypatch.chdir(tmp_path)

        resp = client.get("/api/dashboard/registry")
        skills = resp.json()["skills"]
        assert any(s["name"] == "broken-skill" for s in skills)


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
