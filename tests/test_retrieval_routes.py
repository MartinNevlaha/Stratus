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
            "devrag_available": False,
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
        assert data["devrag_available"] is False


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


class TestRegressionExistingRoutes:
    def test_health_still_returns_200(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
