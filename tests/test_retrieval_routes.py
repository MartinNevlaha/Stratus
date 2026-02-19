"""Tests for retrieval HTTP API routes."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

from stratus.retrieval.models import CorpusType, RetrievalResponse
from stratus.server.app import create_app


@pytest.fixture
def client():
    app = create_app(db_path=":memory:", learning_db_path=":memory:")
    with TestClient(app) as c:
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = RetrievalResponse(
            results=[],
            corpus=CorpusType.CODE,
            query_time_ms=5.0,
        )
        mock_retriever.status.return_value = {
            "vexor_available": True,
            "governance_available": False,
        }
        mock_retriever._vexor.index.return_value = {"status": "ok", "output": "done"}
        c.app.state.retriever = mock_retriever

        mock_cache = MagicMock()
        mock_cache.stats.return_value = {
            "total_entries": 0,
            "total_hits": 0,
            "models": [],
        }
        c.app.state.embed_cache = mock_cache
        yield c


class TestRetrievalSearchRoute:
    def test_retrieval_search_basic(self, client: TestClient):
        resp = client.get("/api/retrieval/search?query=test")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "corpus" in data
        assert "query_time_ms" in data

    def test_retrieval_search_calls_retriever_with_query(self, client: TestClient):
        client.get("/api/retrieval/search?query=myquery")
        retriever = client.app.state.retriever
        retriever.retrieve.assert_called_once()
        call_kwargs = retriever.retrieve.call_args
        assert call_kwargs[0][0] == "myquery"

    def test_retrieval_search_with_corpus(self, client: TestClient):
        resp = client.get("/api/retrieval/search?query=test&corpus=governance")
        assert resp.status_code == 200
        retriever = client.app.state.retriever
        call_kwargs = retriever.retrieve.call_args
        assert call_kwargs[1]["corpus"] == "governance"

    def test_retrieval_search_with_top_k(self, client: TestClient):
        resp = client.get("/api/retrieval/search?query=test&top_k=3")
        assert resp.status_code == 200
        retriever = client.app.state.retriever
        call_kwargs = retriever.retrieve.call_args
        assert call_kwargs[1]["top_k"] == 3

    def test_retrieval_search_missing_query_returns_400(self, client: TestClient):
        resp = client.get("/api/retrieval/search")
        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data

    def test_retrieval_search_default_top_k_is_10(self, client: TestClient):
        client.get("/api/retrieval/search?query=test")
        retriever = client.app.state.retriever
        call_kwargs = retriever.retrieve.call_args
        assert call_kwargs[1]["top_k"] == 10


class TestRetrievalStatusRoute:
    def test_retrieval_status_returns_200(self, client: TestClient):
        resp = client.get("/api/retrieval/status")
        assert resp.status_code == 200

    def test_retrieval_status_returns_availability(self, client: TestClient):
        resp = client.get("/api/retrieval/status")
        data = resp.json()
        assert "vexor_available" in data
        assert data["vexor_available"] is True
        assert data["governance_available"] is False


class TestTriggerIndexRoute:
    def test_trigger_index_returns_202(self, client: TestClient):
        resp = client.post("/api/retrieval/index")
        assert resp.status_code == 202

    def test_trigger_index_returns_ok_status(self, client: TestClient):
        resp = client.post("/api/retrieval/index")
        data = resp.json()
        assert data["status"] == "indexing started"

    def test_trigger_index_calls_vexor_in_background(self, client: TestClient):
        # starlette TestClient (sync) executes background tasks before returning
        mock_retriever = client.app.state.retriever
        client.post("/api/retrieval/index")
        assert mock_retriever._vexor.index.called


class TestIndexStateRoute:
    def test_index_state_returns_200(self, client: TestClient):
        resp = client.get("/api/retrieval/index-state")
        assert resp.status_code == 200

    def test_index_state_returns_status_fields(self, client: TestClient):
        resp = client.get("/api/retrieval/index-state")
        data = resp.json()
        assert "stale" in data
        assert "total_files" in data


class TestEmbedCacheStatsRoute:
    def test_embed_cache_stats_returns_200(self, client: TestClient):
        resp = client.get("/api/retrieval/embed-cache/stats")
        assert resp.status_code == 200

    def test_embed_cache_stats_returns_expected_fields(self, client: TestClient):
        resp = client.get("/api/retrieval/embed-cache/stats")
        data = resp.json()
        assert "total_entries" in data
        assert "total_hits" in data
        assert "models" in data


class TestRetrievalStatusExtended:
    def test_retrieval_status_includes_index_state(self, client: TestClient):
        """GET /api/retrieval/status includes index_state inline."""
        from unittest.mock import patch

        from stratus.retrieval.models import IndexStatus

        known_state = IndexStatus(
            stale=True,
            last_indexed_commit="abc12345",
            total_files=42,
            model="text-embedding-3-small",
        )
        with patch(
            "stratus.retrieval.index_state.read_index_state", return_value=known_state
        ), patch("stratus.session.config.get_data_dir", return_value="/tmp"):
            resp = client.get("/api/retrieval/status")

        assert resp.status_code == 200
        data = resp.json()
        assert "index_state" in data
        assert data["index_state"]["stale"] is True
        assert data["index_state"]["last_indexed_commit"] == "abc12345"
        assert data["index_state"]["total_files"] == 42

    def test_retrieval_status_includes_governance_stats(self, client: TestClient):
        """GET /api/retrieval/status includes governance_stats when retriever provides them."""
        from unittest.mock import patch

        from stratus.retrieval.models import IndexStatus

        gov_stats = {"total_files": 7, "total_chunks": 20, "by_doc_type": {"rule": 5, "adr": 2}}
        client.app.state.retriever.status.return_value = {
            "vexor_available": True,
            "governance_available": True,
            "governance_stats": gov_stats,
        }
        with patch(
            "stratus.retrieval.index_state.read_index_state",
            return_value=IndexStatus(stale=False),
        ), patch("stratus.session.config.get_data_dir", return_value="/tmp"):
            resp = client.get("/api/retrieval/status")

        assert resp.status_code == 200
        data = resp.json()
        assert "governance_stats" in data
        assert data["governance_stats"]["total_files"] == 7


class TestRetrievalStatusLiveVexorStats:
    def test_retrieval_status_merges_live_vexor_show_stats(self, client: TestClient):
        """Merge live vexor stats into /api/retrieval/status response."""
        from unittest.mock import patch

        from stratus.retrieval.models import IndexStatus

        live_stats = {
            "total_files": 312,
            "model": "intfloat/multilingual-e5-small",
            "last_indexed_at": "2026-02-19T11:23:16.928913+00:00",
        }
        client.app.state.retriever._vexor.show.return_value = live_stats

        with patch(
            "stratus.retrieval.index_state.read_index_state",
            return_value=IndexStatus(stale=False),
        ), patch("stratus.session.config.get_data_dir", return_value="/tmp"):
            resp = client.get("/api/retrieval/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["index_state"]["total_files"] == 312
        assert data["index_state"]["model"] == "intfloat/multilingual-e5-small"
        assert data["index_state"]["last_indexed_at"] == "2026-02-19T11:23:16.928913+00:00"

    def test_retrieval_status_show_empty_dict_does_not_overwrite_index_state(
        self, client: TestClient
    ):
        """When vexor show() returns {}, index_state fields from file are not overwritten."""
        from unittest.mock import patch

        from stratus.retrieval.models import IndexStatus

        client.app.state.retriever._vexor.show.return_value = {}

        with patch(
            "stratus.retrieval.index_state.read_index_state",
            return_value=IndexStatus(stale=True, total_files=99),
        ), patch("stratus.session.config.get_data_dir", return_value="/tmp"):
            resp = client.get("/api/retrieval/status")

        assert resp.status_code == 200
        data = resp.json()
        # stale from index-state must still be present
        assert data["index_state"]["stale"] is True
        # total_files from IndexStatus still preserved (show() was empty)
        assert data["index_state"]["total_files"] == 99

    def test_retrieval_status_calls_show_with_project_root(self, client: TestClient):
        """retrieval_status calls vexor.show(path=project_root) from retriever config."""
        from unittest.mock import patch

        from stratus.retrieval.models import IndexStatus

        client.app.state.retriever._vexor.show.return_value = {}
        client.app.state.retriever._config.project_root = "/the/project"

        with patch(
            "stratus.retrieval.index_state.read_index_state",
            return_value=IndexStatus(stale=False),
        ), patch("stratus.session.config.get_data_dir", return_value="/tmp"):
            client.get("/api/retrieval/status")

        client.app.state.retriever._vexor.show.assert_called_once_with(path="/the/project")


class TestTriggerIndexGovernance:
    def test_trigger_index_also_indexes_governance(self, client: TestClient):
        """POST /api/retrieval/index calls index_governance on the retriever."""
        mock_retriever = client.app.state.retriever
        mock_retriever.index_governance.return_value = {"files_indexed": 3}

        client.post("/api/retrieval/index")

        mock_retriever.index_governance.assert_called_once()


class TestRetrievalSearchParamValidation:
    def test_search_invalid_top_k_returns_400(self, client: TestClient):
        resp = client.get("/api/retrieval/search?query=test&top_k=abc")
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_search_large_top_k_is_capped_at_100(self, client: TestClient):
        resp = client.get("/api/retrieval/search?query=test&top_k=9999")
        assert resp.status_code == 200
        retriever = client.app.state.retriever
        call_kwargs = retriever.retrieve.call_args
        assert call_kwargs[1]["top_k"] <= 100

    def test_search_zero_top_k_clamped_to_1(self, client: TestClient):
        resp = client.get("/api/retrieval/search?query=test&top_k=0")
        assert resp.status_code == 200
        retriever = client.app.state.retriever
        call_kwargs = retriever.retrieve.call_args
        assert call_kwargs[1]["top_k"] >= 1


class TestRegressionExistingRoutes:
    def test_health_still_returns_200(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestDoIndexLock:
    """Fix 1: _do_index must serialize via threading.Lock."""

    def test_do_index_skips_when_lock_acquired(self, tmp_path):
        """When lock is already held, _do_index returns without calling vexor."""
        import threading
        from unittest.mock import MagicMock

        from stratus.server.routes_retrieval import _do_index

        mock_retriever = MagicMock()
        lock = threading.Lock()
        lock.acquire()  # Simulate another goroutine holding the lock
        try:
            _do_index(mock_retriever, tmp_path, lock)
        finally:
            lock.release()

        mock_retriever._vexor.index.assert_not_called()

    def test_do_index_releases_lock_on_success(self, tmp_path):
        """After _do_index completes normally, the lock must not be held."""
        import threading
        from unittest.mock import MagicMock

        from stratus.server.routes_retrieval import _do_index

        mock_retriever = MagicMock()
        lock = threading.Lock()
        _do_index(mock_retriever, tmp_path, lock)

        # Lock should be released — acquire(blocking=False) must succeed
        acquired = lock.acquire(blocking=False)
        assert acquired, "Lock was not released after _do_index completed"
        lock.release()

    def test_do_index_releases_lock_on_exception(self, tmp_path):
        """Even when vexor raises, the lock must be released."""
        import threading
        from unittest.mock import MagicMock

        from stratus.server.routes_retrieval import _do_index

        mock_retriever = MagicMock()
        mock_retriever._vexor.index.side_effect = RuntimeError("vexor exploded")
        lock = threading.Lock()
        _do_index(mock_retriever, tmp_path, lock)

        acquired = lock.acquire(blocking=False)
        assert acquired, "Lock was not released after _do_index raised"
        lock.release()

    def test_trigger_index_returns_202_with_lock_available(self, client: TestClient):
        """POST /api/retrieval/index returns 202 when lock is free."""
        resp = client.post("/api/retrieval/index")
        assert resp.status_code == 202


class TestTriggerIndexProjectRoot:
    """Fix 3: project_root validation in trigger_index."""

    def test_trigger_index_skips_if_project_root_mismatch(
        self, client: TestClient, tmp_path
    ):
        """POST with a project_root that does not match server root returns 200 skipped."""
        # Set a known project_root on the retriever config
        client.app.state.retriever._config.project_root = str(tmp_path / "project-a")
        resp = client.post(
            "/api/retrieval/index",
            json={"project_root": str(tmp_path / "project-b")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "skipped"
        assert "mismatch" in data.get("reason", "")

    def test_trigger_index_indexes_if_project_root_matches(
        self, client: TestClient, tmp_path
    ):
        """POST with matching project_root returns 202."""
        project = tmp_path / "my-project"
        client.app.state.retriever._config.project_root = str(project)
        resp = client.post(
            "/api/retrieval/index",
            json={"project_root": str(project)},
        )
        assert resp.status_code == 202

    def test_trigger_index_indexes_if_no_project_root_in_body(self, client: TestClient):
        """POST with empty body still schedules indexing (backward compat)."""
        resp = client.post("/api/retrieval/index", json={})
        assert resp.status_code == 202
