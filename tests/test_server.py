"""Tests for HTTP API server routes."""

import pytest
from starlette.testclient import TestClient

from stratus.server.app import create_app


@pytest.fixture
def client():
    app = create_app(db_path=":memory:", learning_db_path=":memory:")
    with TestClient(app) as c:
        yield c


class TestSystemRoutes:
    def test_health(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_version(self, client: TestClient):
        resp = client.get("/api/version")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data

    def test_stats(self, client: TestClient):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_events" in data
        assert "total_sessions" in data


class TestMemoryRoutes:
    def test_save_memory(self, client: TestClient):
        resp = client.post(
            "/api/memory/save",
            json={
                "text": "found a bug in auth",
                "title": "Auth bug",
                "type": "bugfix",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["id"] >= 1

    def test_save_memory_minimal(self, client: TestClient):
        resp = client.post("/api/memory/save", json={"text": "minimal event"})
        assert resp.status_code == 200
        assert resp.json()["id"] >= 1

    def test_save_memory_missing_text(self, client: TestClient):
        resp = client.post("/api/memory/save", json={"title": "no text"})
        assert resp.status_code == 422

    def test_search(self, client: TestClient):
        # Save something first
        client.post("/api/memory/save", json={"text": "authentication bug in login"})
        client.post("/api/memory/save", json={"text": "database migration"})

        resp = client.get("/api/search", params={"query": "login"})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) >= 1
        assert any("login" in r["text"] for r in data["results"])

    def test_search_with_filters(self, client: TestClient):
        client.post(
            "/api/memory/save",
            json={
                "text": "bug in auth",
                "type": "bugfix",
                "project": "proj-a",
            },
        )
        client.post(
            "/api/memory/save",
            json={
                "text": "auth feature",
                "type": "feature",
                "project": "proj-b",
            },
        )

        resp = client.get(
            "/api/search",
            params={
                "query": "auth",
                "type": "bugfix",
            },
        )
        data = resp.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["type"] == "bugfix"

    def test_search_missing_query(self, client: TestClient):
        resp = client.get("/api/search")
        assert resp.status_code == 400

    def test_timeline(self, client: TestClient):
        ids = []
        for i in range(5):
            r = client.post(
                "/api/memory/save",
                json={
                    "text": f"event {i}",
                    "ts": f"2026-01-01T{i:02d}:00:00Z",
                },
            )
            ids.append(r.json()["id"])

        resp = client.get(
            "/api/timeline",
            params={
                "anchor_id": ids[2],
                "depth_before": 1,
                "depth_after": 1,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert len(data["events"]) == 3

    def test_timeline_missing_anchor(self, client: TestClient):
        resp = client.get("/api/timeline")
        assert resp.status_code == 400

    def test_observations_paginated(self, client: TestClient):
        ids = []
        for i in range(3):
            r = client.post("/api/memory/save", json={"text": f"obs {i}"})
            ids.append(r.json()["id"])

        resp = client.get("/api/observations", params={"ids": ",".join(str(i) for i in ids)})
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert len(data["events"]) == 3

    def test_observations_batch(self, client: TestClient):
        ids = []
        for i in range(3):
            r = client.post("/api/memory/save", json={"text": f"batch {i}"})
            ids.append(r.json()["id"])

        resp = client.post("/api/observations/batch", json={"ids": ids})
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert len(data["events"]) == 3

    def test_observations_batch_missing_ids(self, client: TestClient):
        resp = client.post("/api/observations/batch", json={})
        assert resp.status_code == 400


class TestSessionRoutes:
    def test_session_init(self, client: TestClient):
        resp = client.post(
            "/api/sessions/init",
            json={
                "content_session_id": "cs-123",
                "project": "my-project",
                "prompt": "fix bugs",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["content_session_id"] == "cs-123"
        assert data["project"] == "my-project"

    def test_session_init_missing_fields(self, client: TestClient):
        resp = client.post("/api/sessions/init", json={"project": "p"})
        assert resp.status_code == 422

    def test_list_sessions(self, client: TestClient):
        client.post(
            "/api/sessions/init",
            json={
                "content_session_id": "cs-1",
                "project": "p",
            },
        )
        client.post(
            "/api/sessions/init",
            json={
                "content_session_id": "cs-2",
                "project": "p",
            },
        )

        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert len(data["sessions"]) == 2

    def test_context_inject(self, client: TestClient):
        # Save some events and a session
        client.post(
            "/api/memory/save",
            json={
                "text": "important context",
                "type": "discovery",
                "project": "my-proj",
            },
        )
        client.post(
            "/api/sessions/init",
            json={
                "content_session_id": "cs-1",
                "project": "my-proj",
            },
        )

        resp = client.get("/api/context/inject", params={"project": "my-proj"})
        assert resp.status_code == 200
        data = resp.json()
        assert "context" in data


class TestSaveSearchRoundtrip:
    def test_full_roundtrip(self, client: TestClient):
        """Integration: save → search → get observations."""
        # Save
        save_resp = client.post(
            "/api/memory/save",
            json={
                "text": "discovered memory leak in websocket handler",
                "title": "WebSocket memory leak",
                "type": "bugfix",
                "tags": ["websocket", "memory"],
                "project": "my-app",
            },
        )
        assert save_resp.status_code == 200
        event_id = save_resp.json()["id"]

        # Search
        search_resp = client.get("/api/search", params={"query": "websocket memory"})
        assert search_resp.status_code == 200
        results = search_resp.json()["results"]
        assert len(results) >= 1
        assert any(r["id"] == event_id for r in results)

        # Get observations
        obs_resp = client.post("/api/observations/batch", json={"ids": [event_id]})
        assert obs_resp.status_code == 200
        events = obs_resp.json()["events"]
        assert len(events) == 1
        assert events[0]["text"] == "discovered memory leak in websocket handler"


class TestMemoryParamValidation:
    def test_search_invalid_limit_returns_400(self, client: TestClient):
        resp = client.get("/api/search?query=test&limit=abc")
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_search_invalid_offset_returns_400(self, client: TestClient):
        resp = client.get("/api/search?query=test&offset=xyz")
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_search_large_limit_is_capped(self, client: TestClient):
        resp = client.get("/api/search?query=test&limit=999999")
        assert resp.status_code == 200

    def test_timeline_invalid_anchor_id_returns_400(self, client: TestClient):
        resp = client.get("/api/timeline?anchor_id=notanint")
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_timeline_invalid_depth_before_returns_400(self, client: TestClient):
        # Save an event first so we have a valid anchor
        r = client.post("/api/memory/save", json={"text": "test"})
        anchor_id = r.json()["id"]
        resp = client.get(f"/api/timeline?anchor_id={anchor_id}&depth_before=notanint")
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_timeline_invalid_depth_after_returns_400(self, client: TestClient):
        r = client.post("/api/memory/save", json={"text": "test"})
        anchor_id = r.json()["id"]
        resp = client.get(f"/api/timeline?anchor_id={anchor_id}&depth_after=notanint")
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_timeline_depth_capped(self, client: TestClient):
        r = client.post("/api/memory/save", json={"text": "test"})
        anchor_id = r.json()["id"]
        resp = client.get(f"/api/timeline?anchor_id={anchor_id}&depth_before=9999&depth_after=9999")
        assert resp.status_code == 200

    def test_observations_invalid_ids_returns_400(self, client: TestClient):
        resp = client.get("/api/observations?ids=1,abc,3")
        assert resp.status_code == 400
        assert "error" in resp.json()


class TestSessionParamValidation:
    def test_list_sessions_invalid_limit_returns_400(self, client: TestClient):
        resp = client.get("/api/sessions?limit=abc")
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_list_sessions_invalid_offset_returns_400(self, client: TestClient):
        resp = client.get("/api/sessions?offset=xyz")
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_list_sessions_large_limit_capped(self, client: TestClient):
        resp = client.get("/api/sessions?limit=999999")
        assert resp.status_code == 200


class TestLifespanInitialization:
    def test_learning_db_uses_persistent_path(self, tmp_path, monkeypatch):
        """LearningDatabase must use a file path, not :memory:."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))

        app = create_app(db_path=":memory:")
        with TestClient(app):
            pass
        # A persistent learning.db file should exist in the data dir
        assert (tmp_path / "learning.db").exists()

    def test_learning_config_loads_from_file(self, tmp_path, monkeypatch):
        """LearningConfig should use load_learning_config(), not bare defaults."""
        import json

        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        monkeypatch.chdir(tmp_path)

        # Write a config file that enables learning with aggressive sensitivity
        ai_config = tmp_path / ".ai-framework.json"
        ai_config.write_text(
            json.dumps(
                {
                    "learning": {
                        "global_enabled": True,
                        "sensitivity": "aggressive",
                    },
                }
            )
        )

        app = create_app(db_path=":memory:")
        with TestClient(app):
            config = app.state.learning_config
            assert config.global_enabled is True
            assert config.sensitivity.value == "aggressive"

    def test_governance_store_index_project_called_at_startup(self, tmp_path, monkeypatch):
        """index_project must be called on startup so governance docs are searchable."""
        from unittest.mock import patch

        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        # index_project is gated on .ai-framework.json presence
        (tmp_path / ".ai-framework.json").write_text("{}")

        with patch(
            "stratus.retrieval.governance_store.GovernanceStore.index_project"
        ) as mock_index:
            app = create_app(db_path=":memory:", learning_db_path=":memory:")
            with TestClient(app):
                mock_index.assert_called_once()

    def test_retrieval_config_project_root_set_from_cwd(self, tmp_path, monkeypatch):
        """project_root must be set from cwd so vexor always has a valid path."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        monkeypatch.chdir(tmp_path)

        app = create_app(db_path=":memory:", learning_db_path=":memory:")
        with TestClient(app):
            assert app.state.retriever._config.project_root is not None
            assert app.state.retriever._config.project_root == str(tmp_path.resolve())

    def test_app_skips_governance_indexing_if_no_ai_framework_json(
        self, tmp_path, monkeypatch
    ):
        """When .ai-framework.json is absent, index_project must NOT be called."""
        from unittest.mock import patch

        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        # Ensure .ai-framework.json does NOT exist
        assert not (tmp_path / ".ai-framework.json").exists()

        with patch(
            "stratus.retrieval.governance_store.GovernanceStore.index_project"
        ) as mock_index:
            app = create_app(db_path=":memory:", learning_db_path=":memory:")
            with TestClient(app):
                mock_index.assert_not_called()

    def test_app_indexes_governance_if_ai_framework_json_exists(
        self, tmp_path, monkeypatch
    ):
        """When .ai-framework.json is present, index_project must be called once."""
        from unittest.mock import patch

        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".ai-framework.json").write_text("{}")

        with patch(
            "stratus.retrieval.governance_store.GovernanceStore.index_project"
        ) as mock_index:
            app = create_app(db_path=":memory:", learning_db_path=":memory:")
            with TestClient(app):
                mock_index.assert_called_once()
