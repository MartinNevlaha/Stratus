"""Tests for skills and rules HTTP API routes."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from stratus.rule_engine.models import (
    ImmutabilityViolation,
    Invariant,
    Rule,
    RuleSource,
    RulesSnapshot,
)
from stratus.server.app import create_app
from stratus.skills.models import SkillManifest, SkillValidationError


def _make_skill(name: str, phase: str | None = None) -> SkillManifest:
    return SkillManifest(
        name=name,
        description=f"Desc for {name}",
        agent="framework-expert",
        context="fork",
        requires_phase=phase,
        content_hash="abc123",
    )


def _make_rule(name: str) -> Rule:
    return Rule(
        name=name,
        source=RuleSource.PROJECT,
        content="## Rule\n\nsome content",
        path=f".claude/rules/{name}.md",
        content_hash="def456",
    )


@pytest.fixture
def skill_registry() -> MagicMock:
    skill_a = _make_skill("implement-mcp", phase="plan")
    skill_b = _make_skill("run-tests", phase="verify")
    skill_c = _make_skill("explain-architecture", phase=None)
    skills: dict[str, SkillManifest] = {
        "implement-mcp": skill_a,
        "run-tests": skill_b,
        "explain-architecture": skill_c,
    }

    registry = MagicMock()
    registry.discover.return_value = list(skills.values())
    registry.get.side_effect = lambda name: skills.get(name)
    registry.filter_by_phase.side_effect = lambda phase: [
        s for s in skills.values() if s.requires_phase == phase
    ]
    registry.validate_all.return_value = []
    return registry


@pytest.fixture
def rules_index() -> MagicMock:
    rules = [_make_rule("tdd"), _make_rule("no-mocks")]
    snapshot = RulesSnapshot(rules=rules, snapshot_hash="snap123")
    inv = Invariant(
        id="inv-file-size-limit",
        title="Production files under 300 lines",
        content="500 is hard limit.",
        disablable=True,
    )
    index = MagicMock()
    index.load.return_value = snapshot
    index.get_active_invariants.return_value = [inv]
    index.check_immutability.return_value = []
    return index


@pytest.fixture
def app(skill_registry: MagicMock, rules_index: MagicMock) -> Starlette:
    starlette_app = create_app(db_path=":memory:", learning_db_path=":memory:")
    # TestClient lifespan sets state; we patch after entering the context.
    # We return the app and attach mocks inside the client fixture.
    starlette_app.state.skill_registry = skill_registry  # type: ignore[attr-defined]
    starlette_app.state.rules_index = rules_index  # type: ignore[attr-defined]
    return starlette_app


@pytest.fixture
def client(
    skill_registry: MagicMock,
    rules_index: MagicMock,
) -> Any:
    starlette_app = create_app(db_path=":memory:", learning_db_path=":memory:")
    with TestClient(starlette_app) as c:
        starlette_app.state.skill_registry = skill_registry  # type: ignore[attr-defined]
        starlette_app.state.rules_index = rules_index  # type: ignore[attr-defined]
        yield c, starlette_app


# ------------------------------------------------------------------ #
# GET /api/skills
# ------------------------------------------------------------------ #
class TestListSkills:
    def test_list_skills_returns_200(self, client: Any) -> None:
        c, _ = client
        resp = c.get("/api/skills")
        assert resp.status_code == 200

    def test_list_skills_returns_skills_key(self, client: Any) -> None:
        c, _ = client
        resp = c.get("/api/skills")
        data = resp.json()
        assert "skills" in data
        assert "count" in data

    def test_list_skills_count_matches_skills(self, client: Any) -> None:
        c, _ = client
        resp = c.get("/api/skills")
        data = resp.json()
        assert data["count"] == len(data["skills"])

    def test_list_skills_calls_discover(self, client: Any) -> None:
        c, app = client
        _ = c.get("/api/skills")
        registry: MagicMock = app.state.skill_registry  # type: ignore[attr-defined]
        registry.discover.assert_called_once()

    def test_list_skills_returns_all_skills(self, client: Any) -> None:
        c, _ = client
        resp = c.get("/api/skills")
        data = resp.json()
        assert data["count"] == 3

    def test_skill_has_expected_fields(self, client: Any) -> None:
        c, _ = client
        resp = c.get("/api/skills")
        data = resp.json()
        skill = data["skills"][0]
        assert "name" in skill
        assert "description" in skill
        assert "agent" in skill


# ------------------------------------------------------------------ #
# GET /api/skills/{name}
# ------------------------------------------------------------------ #
class TestGetSkill:
    def test_get_skill_found_returns_200(self, client: Any) -> None:
        c, _ = client
        resp = c.get("/api/skills/implement-mcp")
        assert resp.status_code == 200

    def test_get_skill_found_returns_correct_name(self, client: Any) -> None:
        c, _ = client
        resp = c.get("/api/skills/implement-mcp")
        data = resp.json()
        assert data["name"] == "implement-mcp"

    def test_get_skill_not_found_returns_404(self, client: Any) -> None:
        c, _ = client
        resp = c.get("/api/skills/nonexistent-skill")
        assert resp.status_code == 404

    def test_get_skill_not_found_returns_error(self, client: Any) -> None:
        c, _ = client
        resp = c.get("/api/skills/nonexistent-skill")
        data = resp.json()
        assert "error" in data


# ------------------------------------------------------------------ #
# GET /api/skills/phase/{phase}
# ------------------------------------------------------------------ #
class TestFilterSkillsByPhase:
    def test_filter_by_phase_returns_200(self, client: Any) -> None:
        c, _ = client
        resp = c.get("/api/skills/phase/plan")
        assert resp.status_code == 200

    def test_filter_by_phase_returns_matching_skills(self, client: Any) -> None:
        c, _ = client
        resp = c.get("/api/skills/phase/plan")
        data = resp.json()
        assert "skills" in data
        assert data["count"] == 1
        assert data["skills"][0]["name"] == "implement-mcp"

    def test_filter_by_phase_calls_filter(self, client: Any) -> None:
        c, app = client
        _ = c.get("/api/skills/phase/verify")
        registry: MagicMock = app.state.skill_registry  # type: ignore[attr-defined]
        registry.filter_by_phase.assert_called_with("verify")

    def test_filter_by_phase_empty_returns_zero(self, client: Any) -> None:
        c, _ = client
        resp = c.get("/api/skills/phase/unknown-phase")
        data = resp.json()
        assert data["count"] == 0
        assert data["skills"] == []


# ------------------------------------------------------------------ #
# POST /api/skills/validate
# ------------------------------------------------------------------ #
class TestValidateSkills:
    def test_validate_no_errors_returns_200(self, client: Any) -> None:
        c, _ = client
        resp = c.post("/api/skills/validate")
        assert resp.status_code == 200

    def test_validate_returns_valid_true_when_no_errors(self, client: Any) -> None:
        c, _ = client
        resp = c.post("/api/skills/validate")
        data = resp.json()
        assert data["valid"] is True
        assert data["error_count"] == 0
        assert data["errors"] == []

    def test_validate_returns_errors_when_present(self, client: Any) -> None:
        c, app = client
        err = SkillValidationError(skill_name="broken-skill", message="Agent file missing")
        registry: MagicMock = app.state.skill_registry  # type: ignore[attr-defined]
        registry.validate_all.return_value = [err]

        resp = c.post("/api/skills/validate")
        data = resp.json()
        assert data["valid"] is False
        assert data["error_count"] == 1
        assert data["errors"][0]["skill_name"] == "broken-skill"

    def test_validate_calls_validate_all(self, client: Any) -> None:
        c, app = client
        _ = c.post("/api/skills/validate")
        registry: MagicMock = app.state.skill_registry  # type: ignore[attr-defined]
        registry.validate_all.assert_called_once()


# ------------------------------------------------------------------ #
# GET /api/rules
# ------------------------------------------------------------------ #
class TestListRules:
    def test_list_rules_returns_200(self, client: Any) -> None:
        c, _ = client
        resp = c.get("/api/rules")
        assert resp.status_code == 200

    def test_list_rules_returns_rules_key(self, client: Any) -> None:
        c, _ = client
        resp = c.get("/api/rules")
        data = resp.json()
        assert "rules" in data
        assert "count" in data
        assert "snapshot_hash" in data

    def test_list_rules_calls_load(self, client: Any) -> None:
        c, app = client
        _ = c.get("/api/rules")
        index: MagicMock = app.state.rules_index  # type: ignore[attr-defined]
        index.load.assert_called_once()

    def test_list_rules_count_is_correct(self, client: Any) -> None:
        c, _ = client
        resp = c.get("/api/rules")
        data = resp.json()
        assert data["count"] == 2

    def test_rule_has_expected_fields(self, client: Any) -> None:
        c, _ = client
        resp = c.get("/api/rules")
        data = resp.json()
        rule = data["rules"][0]
        assert "name" in rule
        assert "source" in rule
        assert "content_hash" in rule


# ------------------------------------------------------------------ #
# GET /api/rules/invariants
# ------------------------------------------------------------------ #
class TestListInvariants:
    def test_list_invariants_returns_200(self, client: Any) -> None:
        c, _ = client
        resp = c.get("/api/rules/invariants")
        assert resp.status_code == 200

    def test_list_invariants_returns_invariants_key(self, client: Any) -> None:
        c, _ = client
        resp = c.get("/api/rules/invariants")
        data = resp.json()
        assert "invariants" in data
        assert "count" in data

    def test_list_invariants_calls_get_active(self, client: Any) -> None:
        c, app = client
        _ = c.get("/api/rules/invariants")
        index: MagicMock = app.state.rules_index  # type: ignore[attr-defined]
        index.get_active_invariants.assert_called_once()

    def test_list_invariants_count_is_correct(self, client: Any) -> None:
        c, _ = client
        resp = c.get("/api/rules/invariants")
        data = resp.json()
        assert data["count"] == 1

    def test_invariant_has_expected_fields(self, client: Any) -> None:
        c, _ = client
        resp = c.get("/api/rules/invariants")
        data = resp.json()
        inv = data["invariants"][0]
        assert "id" in inv
        assert "title" in inv
        assert "disablable" in inv

    def test_list_invariants_passes_disabled_ids(self, client: Any) -> None:
        c, app = client
        _ = c.get("/api/rules/invariants?disabled=inv-file-size-limit,inv-no-new-deps")
        index: MagicMock = app.state.rules_index  # type: ignore[attr-defined]
        call_args = index.get_active_invariants.call_args
        disabled: list[str] = call_args[1].get("disabled_ids") or call_args[0][0]
        assert "inv-file-size-limit" in disabled


# ------------------------------------------------------------------ #
# POST /api/rules/check-immutability
# ------------------------------------------------------------------ #
class TestCheckImmutability:
    def test_check_immutability_returns_200(self, client: Any) -> None:
        c, _ = client
        snapshot = RulesSnapshot(rules=[], snapshot_hash="abc")
        resp = c.post("/api/rules/check-immutability", json=snapshot.model_dump())
        assert resp.status_code == 200

    def test_check_immutability_no_violations(self, client: Any) -> None:
        c, _ = client
        snapshot = RulesSnapshot(rules=[], snapshot_hash="abc")
        resp = c.post("/api/rules/check-immutability", json=snapshot.model_dump())
        data = resp.json()
        assert data["immutable"] is True
        assert data["violation_count"] == 0
        assert data["violations"] == []

    def test_check_immutability_with_violations(self, client: Any) -> None:
        c, app = client
        violation = ImmutabilityViolation(
            rule_name="tdd",
            change_type="modified",
            details="Rule 'tdd' content changed",
        )
        index: MagicMock = app.state.rules_index  # type: ignore[attr-defined]
        index.check_immutability.return_value = [violation]

        snapshot = RulesSnapshot(rules=[], snapshot_hash="abc")
        resp = c.post("/api/rules/check-immutability", json=snapshot.model_dump())
        data = resp.json()
        assert data["immutable"] is False
        assert data["violation_count"] == 1
        assert data["violations"][0]["rule_name"] == "tdd"

    def test_check_immutability_invalid_body_returns_422(self, client: Any) -> None:
        c, _ = client
        resp = c.post("/api/rules/check-immutability", content=b"not-json")
        assert resp.status_code == 422

    def test_check_immutability_calls_index(self, client: Any) -> None:
        c, app = client
        snapshot = RulesSnapshot(rules=[], snapshot_hash="abc")
        _ = c.post("/api/rules/check-immutability", json=snapshot.model_dump())
        index: MagicMock = app.state.rules_index  # type: ignore[attr-defined]
        index.check_immutability.assert_called_once()


# ------------------------------------------------------------------ #
# Regression: other routes still work
# ------------------------------------------------------------------ #
class TestRegressionExistingRoutes:
    def test_health_still_returns_200(self, client: Any) -> None:
        c, _ = client
        resp = c.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
