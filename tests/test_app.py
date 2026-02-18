"""Tests for app.py lifespan initialization — skills and rules subsystem state."""

from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from stratus.rule_engine.index import RulesIndex
from stratus.server.app import create_app
from stratus.skills.registry import SkillRegistry


@pytest.fixture
def app() -> Starlette:
    return create_app(db_path=":memory:", learning_db_path=":memory:")


class TestLifespanSkillsRulesState:
    def test_skill_registry_initialized_on_state(self, app: Starlette) -> None:
        with TestClient(app):
            registry = app.state.skill_registry  # type: ignore[attr-defined]
            assert isinstance(registry, SkillRegistry)

    def test_rules_index_initialized_on_state(self, app: Starlette) -> None:
        with TestClient(app):
            index = app.state.rules_index  # type: ignore[attr-defined]
            assert isinstance(index, RulesIndex)

    def test_skills_route_accessible_after_lifespan(self, app: Starlette) -> None:
        with TestClient(app) as c:
            resp = c.get("/api/skills")
            assert resp.status_code == 200

    def test_rules_route_accessible_after_lifespan(self, app: Starlette) -> None:
        with TestClient(app) as c:
            resp = c.get("/api/rules")
            assert resp.status_code == 200
