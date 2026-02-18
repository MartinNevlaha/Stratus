"""Tests for server/routes_analytics.py — HTTP API routes for failure analytics."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from stratus.learning.database import LearningDatabase
from stratus.learning.models import (
    FailureCategory,
    FailureEvent,
    RuleBaseline,
)
from stratus.server.app import create_app


@pytest.fixture
def client():
    app = create_app(":memory:", learning_db_path=":memory:")
    with TestClient(app) as c:
        yield c


class TestRecordFailureEndpoint:
    def test_post_valid_failure_returns_id_and_signature(self, client: TestClient):
        resp = client.post(
            "/api/learning/analytics/record-failure",
            json={
                "category": "lint_error",
                "file_path": "src/foo.py",
                "detail": "E501 line too long",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert "signature" in data
        assert len(data["signature"]) == 16  # SHA256[:16]

    def test_post_without_category_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/learning/analytics/record-failure",
            json={"file_path": "src/foo.py"},
        )
        assert resp.status_code == 422
        assert "error" in resp.json()

    def test_post_duplicate_same_signature_count_stays_1(self, client: TestClient):
        payload = {
            "category": "missing_test",
            "file_path": "src/bar.py",
            "detail": "no test",
        }
        resp1 = client.post("/api/learning/analytics/record-failure", json=payload)
        resp2 = client.post("/api/learning/analytics/record-failure", json=payload)

        assert resp1.status_code == 200
        assert resp2.status_code == 200

        # Both return the same signature (dedup key)
        assert resp1.json()["signature"] == resp2.json()["signature"]

        db: LearningDatabase = client.app.state.learning_db
        count = db.analytics.count_failures(FailureCategory.MISSING_TEST)
        assert count == 1


class TestFailureSummaryEndpoint:
    def test_get_summary_empty_db_returns_zero(self, client: TestClient):
        resp = client.get("/api/learning/analytics/failures/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_failures"] == 0
        assert "period_days" in data
        assert "daily_rate" in data

    def test_get_summary_with_seeded_data(self, client: TestClient):
        db: LearningDatabase = client.app.state.learning_db
        for i in range(3):
            db.analytics.record_failure(
                FailureEvent(
                    category=FailureCategory.LINT_ERROR,
                    detail=f"error {i}",
                )
            )

        resp = client.get("/api/learning/analytics/failures/summary?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_failures"] == 3
        assert "lint_error" in data["by_category"]


class TestFailureTrendsEndpoint:
    def test_get_trends_empty_db_returns_list(self, client: TestClient):
        resp = client.get("/api/learning/analytics/failures/trends")
        assert resp.status_code == 200
        data = resp.json()
        assert "trends" in data
        assert isinstance(data["trends"], list)

    def test_get_trends_with_category_filter(self, client: TestClient):
        db: LearningDatabase = client.app.state.learning_db
        db.analytics.record_failure(
            FailureEvent(
                category=FailureCategory.LINT_ERROR,
                detail="ruff error",
            )
        )
        resp = client.get("/api/learning/analytics/failures/trends?category=lint_error")
        assert resp.status_code == 200
        data = resp.json()
        assert "trends" in data


class TestFailureHotspotsEndpoint:
    def test_get_hotspots_empty_db_returns_list(self, client: TestClient):
        resp = client.get("/api/learning/analytics/failures/hotspots")
        assert resp.status_code == 200
        data = resp.json()
        assert "hotspots" in data
        assert isinstance(data["hotspots"], list)

    def test_get_hotspots_respects_limit_param(self, client: TestClient):
        db: LearningDatabase = client.app.state.learning_db
        for i in range(5):
            db.analytics.record_failure(
                FailureEvent(
                    category=FailureCategory.LINT_ERROR,
                    file_path=f"src/file{i}.py",
                    detail="error",
                )
            )

        resp = client.get("/api/learning/analytics/failures/hotspots?limit=3")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["hotspots"]) <= 3


class TestSystematicProblemsEndpoint:
    def test_get_systematic_empty_returns_list(self, client: TestClient):
        resp = client.get("/api/learning/analytics/failures/systematic")
        assert resp.status_code == 200
        data = resp.json()
        assert "problems" in data
        assert isinstance(data["problems"], list)


class TestRulesEffectivenessEndpoint:
    def test_get_effectiveness_empty_returns_rules_list(self, client: TestClient):
        resp = client.get("/api/learning/analytics/rules/effectiveness")
        assert resp.status_code == 200
        data = resp.json()
        assert "rules" in data
        assert isinstance(data["rules"], list)

    def test_get_effectiveness_with_baseline(self, client: TestClient):
        db: LearningDatabase = client.app.state.learning_db
        db.analytics.save_baseline(
            RuleBaseline(
                proposal_id="p1",
                rule_path=".claude/rules/test.md",
                category=FailureCategory.LINT_ERROR,
                baseline_count=10,
                baseline_window_days=30,
            )
        )

        resp = client.get("/api/learning/analytics/rules/effectiveness")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["rules"]) == 1
        rule = data["rules"][0]
        assert "verdict" in rule
        assert "effectiveness_score" in rule


class TestRulesLowImpactEndpoint:
    def test_get_low_impact_filters_effective_rules(self, client: TestClient):
        db: LearningDatabase = client.app.state.learning_db
        # Save a baseline — with no post-baseline failures, score=1.0 → "effective"
        db.analytics.save_baseline(
            RuleBaseline(
                proposal_id="p1",
                rule_path=".claude/rules/test.md",
                category=FailureCategory.LINT_ERROR,
                baseline_count=0,
                baseline_window_days=30,
            )
        )

        resp = client.get("/api/learning/analytics/rules/low-impact")
        assert resp.status_code == 200
        data = resp.json()
        assert "rules" in data
        assert "count" in data
        # All effective rules should be excluded
        for rule in data["rules"]:
            assert rule["verdict"] != "effective"

    def test_get_low_impact_empty_db(self, client: TestClient):
        resp = client.get("/api/learning/analytics/rules/low-impact")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["rules"] == []
