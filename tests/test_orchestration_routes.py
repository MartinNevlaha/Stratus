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


def _start_and_approve(client: TestClient, slug: str = "feat", total_tasks: int = 3) -> None:
    """Helper: start a spec and approve the plan so we are in implement phase."""
    client.post("/api/orchestration/start", json={"slug": slug})
    client.post("/api/orchestration/approve-plan", json={"total_tasks": total_tasks})


class TestStartTask:
    def test_start_task(self, client: TestClient):
        _start_and_approve(client)
        resp = client.post("/api/orchestration/start-task", json={"task_num": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "implement"
        assert data["current_task"] == 2

    def test_start_task_with_agent_id(self, client: TestClient):
        _start_and_approve(client)
        resp = client.post(
            "/api/orchestration/start-task",
            json={"task_num": 2, "agent_id": "mobile-dev-specialist"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "implement"
        assert data["current_task"] == 2
        assert data["active_agent_id"] == "mobile-dev-specialist"

    def test_start_task_with_agent_id_reflected_in_state(self, client: TestClient):
        _start_and_approve(client)
        client.post(
            "/api/orchestration/start-task", json={"task_num": 1, "agent_id": "backend-dev"}
        )
        resp = client.get("/api/orchestration/state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_agent_id"] == "backend-dev"

    def test_start_task_no_spec(self, client: TestClient):
        resp = client.post("/api/orchestration/start-task", json={"task_num": 1})
        assert resp.status_code == 409

    def test_start_task_missing_task_num(self, client: TestClient):
        _start_and_approve(client)
        resp = client.post("/api/orchestration/start-task", json={})
        assert resp.status_code == 422

    def test_start_task_invalid_json(self, client: TestClient):
        resp = client.post(
            "/api/orchestration/start-task",
            content="not-json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 422


class TestCompleteTask:
    def test_complete_task(self, client: TestClient):
        _start_and_approve(client, total_tasks=3)
        resp = client.post("/api/orchestration/complete-task", json={"task_num": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "implement"
        assert data["completed_tasks"] == 1
        assert "current_task" in data
        assert data["all_done"] is False

    def test_complete_all_tasks(self, client: TestClient):
        _start_and_approve(client, total_tasks=1)
        resp = client.post("/api/orchestration/complete-task", json={"task_num": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["all_done"] is True

    def test_complete_task_no_spec(self, client: TestClient):
        resp = client.post("/api/orchestration/complete-task", json={"task_num": 1})
        assert resp.status_code == 409

    def test_complete_task_missing_task_num(self, client: TestClient):
        _start_and_approve(client)
        resp = client.post("/api/orchestration/complete-task", json={})
        assert resp.status_code == 422


class TestSetActiveAgent:
    def test_set_active_agent(self, client: TestClient):
        _start_and_approve(client)
        resp = client.post(
            "/api/orchestration/set-active-agent",
            json={"agent_id": "mobile-dev-specialist"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_agent_id"] == "mobile-dev-specialist"

    def test_set_active_agent_clears(self, client: TestClient):
        _start_and_approve(client)
        client.post(
            "/api/orchestration/set-active-agent",
            json={"agent_id": "mobile-dev-specialist"},
        )
        resp = client.post(
            "/api/orchestration/set-active-agent",
            json={"agent_id": None},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_agent_id"] is None

    def test_set_active_agent_no_spec(self, client: TestClient):
        resp = client.post(
            "/api/orchestration/set-active-agent",
            json={"agent_id": "some-agent"},
        )
        assert resp.status_code == 409

    def test_set_active_agent_reflected_in_state(self, client: TestClient):
        _start_and_approve(client)
        client.post(
            "/api/orchestration/set-active-agent",
            json={"agent_id": "backend-dev"},
        )
        resp = client.get("/api/orchestration/state")
        assert resp.status_code == 200
        assert resp.json()["active_agent_id"] == "backend-dev"


class TestStartVerify:
    def test_start_verify(self, client: TestClient):
        _start_and_approve(client)
        resp = client.post("/api/orchestration/start-verify")
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "verify"
        assert data["plan_status"] == "verifying"

    def test_start_verify_no_spec(self, client: TestClient):
        resp = client.post("/api/orchestration/start-verify")
        assert resp.status_code == 409

    def test_start_verify_wrong_phase(self, client: TestClient):
        # Cannot transition from plan directly to verify
        client.post("/api/orchestration/start", json={"slug": "feat"})
        resp = client.post("/api/orchestration/start-verify")
        assert resp.status_code == 409


class TestRecordVerdicts:
    def _passing_verdict(self) -> dict:
        return {
            "reviewer": "delivery-spec-reviewer-quality",
            "verdict": "pass",
            "findings": [],
            "raw_output": "Verdict: PASS",
        }

    def _failing_verdict(self) -> dict:
        return {
            "reviewer": "delivery-spec-reviewer-compliance",
            "verdict": "fail",
            "findings": [
                {
                    "file_path": "src/app.py",
                    "line": 10,
                    "severity": "must_fix",
                    "description": "Missing type hint",
                }
            ],
            "raw_output": "Verdict: FAIL\n- must_fix: src/app.py:10 — Missing type hint",
        }

    def test_record_passing_verdicts(self, client: TestClient):
        resp = client.post(
            "/api/orchestration/record-verdicts",
            json={"verdicts": [self._passing_verdict()]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["all_passed"] is True
        assert data["needs_fix"] is False
        assert data["total_findings"] == 0

    def test_record_failing_verdicts(self, client: TestClient):
        _start_and_approve(client)
        client.post("/api/orchestration/start-verify")
        resp = client.post(
            "/api/orchestration/record-verdicts",
            json={"verdicts": [self._failing_verdict()]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["all_passed"] is False
        assert data["failed_reviewers"] == ["delivery-spec-reviewer-compliance"]
        assert data["must_fix_count"] == 1
        assert "needs_fix" in data

    def test_record_verdicts_missing_verdicts_key(self, client: TestClient):
        resp = client.post("/api/orchestration/record-verdicts", json={})
        assert resp.status_code == 422

    def test_record_verdicts_invalid_json(self, client: TestClient):
        resp = client.post(
            "/api/orchestration/record-verdicts",
            content="bad",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 422

    def test_record_verdicts_invalid_verdict_object(self, client: TestClient):
        resp = client.post(
            "/api/orchestration/record-verdicts",
            json={"verdicts": [{"bad": "data"}]},
        )
        assert resp.status_code == 409


class TestStartFixLoop:
    def test_start_fix_loop(self, client: TestClient):
        _start_and_approve(client)
        client.post("/api/orchestration/start-verify")
        resp = client.post("/api/orchestration/start-fix-loop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "implement"
        assert data["review_iteration"] == 1

    def test_start_fix_loop_no_spec(self, client: TestClient):
        resp = client.post("/api/orchestration/start-fix-loop")
        assert resp.status_code == 409


class TestStartLearn:
    def test_start_learn(self, client: TestClient):
        _start_and_approve(client)
        client.post("/api/orchestration/start-verify")
        resp = client.post("/api/orchestration/start-learn")
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "learn"

    def test_start_learn_no_spec(self, client: TestClient):
        resp = client.post("/api/orchestration/start-learn")
        assert resp.status_code == 409


class TestCompleteSpec:
    def test_complete_spec(self, client: TestClient):
        _start_and_approve(client)
        client.post("/api/orchestration/start-verify")
        client.post("/api/orchestration/start-learn")
        resp = client.post("/api/orchestration/complete")
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "complete"
        assert data["plan_status"] == "complete"

    def test_complete_spec_returns_inactive(self, client: TestClient):
        _start_and_approve(client)
        client.post("/api/orchestration/start-verify")
        client.post("/api/orchestration/start-learn")
        client.post("/api/orchestration/complete")
        resp = client.get("/api/orchestration/state")
        assert resp.json()["active"] is False

    def test_complete_spec_no_spec(self, client: TestClient):
        resp = client.post("/api/orchestration/complete")
        assert resp.status_code == 409
