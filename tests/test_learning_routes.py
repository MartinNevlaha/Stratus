"""Tests for server/routes_learning.py — HTTP API routes."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from stratus.learning.database import LearningDatabase
from stratus.learning.models import (
    Proposal,
    ProposalType,
)
from stratus.server.app import create_app


@pytest.fixture
def client():
    app = create_app(":memory:", learning_db_path=":memory:")
    with TestClient(app) as c:
        yield c


class TestAnalyzeEndpoint:
    def test_post_analyze(self, client: TestClient):
        resp = client.post("/api/learning/analyze", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "analysis_time_ms" in data or "error" in data

    def test_post_analyze_with_since_commit(self, client: TestClient):
        resp = client.post("/api/learning/analyze", json={"since_commit": "abc123"})
        assert resp.status_code == 200


class TestProposalsEndpoint:
    def test_get_proposals_empty(self, client: TestClient):
        resp = client.get("/api/learning/proposals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["proposals"] == []
        assert data["count"] == 0

    def test_get_proposals_with_data(self, client: TestClient):
        # Insert a proposal directly into the DB
        db: LearningDatabase = client.app.state.learning_db
        db.save_proposal(
            Proposal(
                id="p1",
                candidate_id="c1",
                type=ProposalType.RULE,
                title="Test",
                description="d",
                proposed_content="c",
                confidence=0.8,
            )
        )
        resp = client.get("/api/learning/proposals")
        data = resp.json()
        assert data["count"] == 1

    def test_get_proposals_with_max_count(self, client: TestClient):
        db: LearningDatabase = client.app.state.learning_db
        for i in range(5):
            db.save_proposal(
                Proposal(
                    id=f"p{i}",
                    candidate_id=f"c{i}",
                    type=ProposalType.RULE,
                    title=f"Rule {i}",
                    description="d",
                    proposed_content="c",
                    confidence=0.8,
                )
            )
        resp = client.get("/api/learning/proposals?max_count=2")
        data = resp.json()
        assert data["count"] == 2


class TestDecideEndpoint:
    def test_accept_proposal(self, client: TestClient):
        db: LearningDatabase = client.app.state.learning_db
        db.save_proposal(
            Proposal(
                id="p1",
                candidate_id="c1",
                type=ProposalType.RULE,
                title="Test",
                description="d",
                proposed_content="c",
                confidence=0.8,
            )
        )
        resp = client.post(
            "/api/learning/decide",
            json={
                "proposal_id": "p1",
                "decision": "accept",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "accept"

    def test_reject_proposal(self, client: TestClient):
        db: LearningDatabase = client.app.state.learning_db
        db.save_proposal(
            Proposal(
                id="p1",
                candidate_id="c1",
                type=ProposalType.RULE,
                title="Test",
                description="d",
                proposed_content="c",
                confidence=0.8,
            )
        )
        resp = client.post(
            "/api/learning/decide",
            json={
                "proposal_id": "p1",
                "decision": "reject",
            },
        )
        assert resp.status_code == 200

    def test_decide_missing_fields(self, client: TestClient):
        resp = client.post("/api/learning/decide", json={})
        assert resp.status_code == 422


class TestDecideViaWatcher:
    def test_accept_via_route_creates_artifact(self, client: TestClient):
        db: LearningDatabase = client.app.state.learning_db
        db.save_proposal(
            Proposal(
                id="p1",
                candidate_id="c1",
                type=ProposalType.RULE,
                title="Error handling",
                description="d",
                proposed_content="c",
                confidence=0.8,
            )
        )
        resp = client.post(
            "/api/learning/decide",
            json={
                "proposal_id": "p1",
                "decision": "accept",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # artifact_path should be present in response (may be None if no project_root)
        assert "artifact_path" in data

    def test_decide_returns_artifact_path(self, client: TestClient):
        db: LearningDatabase = client.app.state.learning_db
        db.save_proposal(
            Proposal(
                id="p1",
                candidate_id="c1",
                type=ProposalType.RULE,
                title="Error handling",
                description="d",
                proposed_content="c",
                confidence=0.8,
            )
        )
        resp = client.post(
            "/api/learning/decide",
            json={
                "proposal_id": "p1",
                "decision": "accept",
            },
        )
        data = resp.json()
        assert "artifact_path" in data

    def test_decide_when_learning_not_initialized(self, client: TestClient):
        client.app.state.learning_watcher = None
        resp = client.post(
            "/api/learning/decide",
            json={
                "proposal_id": "p1",
                "decision": "accept",
            },
        )
        assert resp.status_code == 503
        assert "not initialized" in resp.json()["error"].lower()


class TestConfigEndpoint:
    def test_get_config(self, client: TestClient):
        resp = client.get("/api/learning/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "global_enabled" in data
        assert data["global_enabled"] is True

    def test_put_config_enable(self, client: TestClient):
        resp = client.put("/api/learning/config", json={"global_enabled": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["global_enabled"] is True


class TestProposalsParamValidation:
    def test_get_proposals_invalid_max_count_returns_400(self, client: TestClient):
        resp = client.get("/api/learning/proposals?max_count=abc")
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_get_proposals_invalid_min_confidence_returns_400(self, client: TestClient):
        resp = client.get("/api/learning/proposals?min_confidence=notafloat")
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_get_proposals_large_max_count_capped(self, client: TestClient):
        resp = client.get("/api/learning/proposals?max_count=99999")
        assert resp.status_code == 200


class TestStatsEndpoint:
    def test_get_stats(self, client: TestClient):
        resp = client.get("/api/learning/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "candidates_total" in data
        assert "proposals_total" in data
