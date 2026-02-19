"""Tests for retrieval/unified.py — UnifiedRetriever."""

from __future__ import annotations

from unittest.mock import MagicMock

from stratus.retrieval.models import CorpusType, RetrievalResponse, SearchResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(
    results: list[SearchResult] | None = None,
    corpus: CorpusType = CorpusType.CODE,
    query_time_ms: float = 10.0,
) -> RetrievalResponse:
    return RetrievalResponse(
        results=results or [],
        corpus=corpus,
        query_time_ms=query_time_ms,
    )


def _make_result(
    file_path: str = "test.py",
    score: float = 0.9,
    rank: int = 1,
    excerpt: str = "test",
) -> SearchResult:
    return SearchResult(file_path=file_path, score=score, rank=rank, excerpt=excerpt)


def _make_vexor_mock(
    results: list[SearchResult] | None = None, available: bool = True
) -> MagicMock:
    mock = MagicMock()
    mock.is_available.return_value = available
    mock.search.return_value = _make_response(results=results, corpus=CorpusType.CODE)
    return mock


def _make_devrag_mock(
    results: list[SearchResult] | None = None, available: bool = True
) -> MagicMock:
    mock = MagicMock()
    mock.is_available.return_value = available
    mock.search.return_value = _make_response(results=results, corpus=CorpusType.GOVERNANCE)
    return mock


# ---------------------------------------------------------------------------
# TestRetrieve
# ---------------------------------------------------------------------------

class TestRetrieve:
    def test_retrieve_explicit_code_corpus(self):
        """corpus='code' routes to VexorClient.search."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock([_make_result("src/main.py", score=0.95)])
        devrag = _make_devrag_mock()
        retriever = UnifiedRetriever(vexor=vexor, devrag=devrag)

        response = retriever.retrieve("find the main function", corpus="code", top_k=5)

        vexor.search.assert_called_once_with("find the main function", top=5, path=None)
        devrag.search.assert_not_called()
        assert response.corpus == CorpusType.CODE
        assert len(response.results) == 1

    def test_retrieve_explicit_governance_corpus(self):
        """corpus='governance' routes to DevRagClient.search."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock()
        devrag = _make_devrag_mock([_make_result("policy.md", score=0.88)])
        retriever = UnifiedRetriever(vexor=vexor, devrag=devrag)

        response = retriever.retrieve("naming convention", corpus="governance", top_k=3)

        devrag.search.assert_called_once_with("naming convention", top_k=3)
        vexor.search.assert_not_called()
        assert response.corpus == CorpusType.GOVERNANCE
        assert len(response.results) == 1

    def test_retrieve_auto_classifies_code_query(self):
        """'where is the function' → classify_query → 'code' → Vexor."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock([_make_result()])
        devrag = _make_devrag_mock()
        retriever = UnifiedRetriever(vexor=vexor, devrag=devrag)

        response = retriever.retrieve("where is the function defined")

        vexor.search.assert_called_once()
        devrag.search.assert_not_called()
        assert response.corpus == CorpusType.CODE

    def test_retrieve_auto_classifies_rule_query(self):
        """'what is the naming convention' → classify_query → 'rule' → DevRag."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock()
        devrag = _make_devrag_mock([_make_result("rules.md", score=0.7)])
        retriever = UnifiedRetriever(vexor=vexor, devrag=devrag)

        response = retriever.retrieve("what is the naming convention")

        devrag.search.assert_called_once()
        vexor.search.assert_not_called()
        assert response.corpus == CorpusType.GOVERNANCE

    def test_retrieve_auto_classifies_general_query(self):
        """'python 3.12' → classify_query → 'general' → Vexor."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock([_make_result()])
        devrag = _make_devrag_mock()
        retriever = UnifiedRetriever(vexor=vexor, devrag=devrag)

        retriever.retrieve("python 3.12")

        vexor.search.assert_called_once()
        devrag.search.assert_not_called()

    def test_retrieve_fallback_when_vexor_fails(self):
        """If Vexor raises, falls back to DevRag."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock()
        vexor.search.side_effect = RuntimeError("vexor unavailable")
        devrag = _make_devrag_mock([_make_result("fallback.py", score=0.5)])
        retriever = UnifiedRetriever(vexor=vexor, devrag=devrag)

        response = retriever.retrieve("find the main function", corpus="code")

        devrag.search.assert_called_once()
        assert len(response.results) == 1
        assert response.results[0].file_path == "fallback.py"

    def test_retrieve_fallback_when_devrag_fails(self):
        """If DevRag raises, falls back to Vexor."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock([_make_result("vexor_result.py", score=0.8)])
        devrag = _make_devrag_mock()
        devrag.search.side_effect = RuntimeError("devrag unavailable")
        retriever = UnifiedRetriever(vexor=vexor, devrag=devrag)

        response = retriever.retrieve("naming convention", corpus="governance")

        vexor.search.assert_called_once()
        assert len(response.results) == 1
        assert response.results[0].file_path == "vexor_result.py"

    def test_retrieve_returns_empty_when_both_fail(self):
        """If both backends raise, returns empty RetrievalResponse."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock()
        vexor.search.side_effect = RuntimeError("vexor unavailable")
        devrag = _make_devrag_mock()
        devrag.search.side_effect = RuntimeError("devrag unavailable")
        retriever = UnifiedRetriever(vexor=vexor, devrag=devrag)

        response = retriever.retrieve("find the main function", corpus="code")

        assert response.results == []


# ---------------------------------------------------------------------------
# TestRetrieveHybrid
# ---------------------------------------------------------------------------

class TestRetrieveHybrid:
    def test_hybrid_merges_both_backends(self):
        """retrieve_hybrid queries both Vexor and DevRag and combines results."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor_results = [_make_result("a.py", score=0.9, rank=1)]
        devrag_results = [_make_result("b.md", score=0.8, rank=1)]
        vexor = _make_vexor_mock(vexor_results)
        devrag = _make_devrag_mock(devrag_results)
        retriever = UnifiedRetriever(vexor=vexor, devrag=devrag)

        response = retriever.retrieve_hybrid("some query")

        vexor.search.assert_called_once()
        devrag.search.assert_called_once()
        assert len(response.results) == 2

    def test_hybrid_deduplicates_by_file_path(self):
        """retrieve_hybrid keeps highest score when same file_path appears in both."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor_results = [_make_result("shared.py", score=0.9, rank=1)]
        devrag_results = [_make_result("shared.py", score=0.7, rank=1)]
        vexor = _make_vexor_mock(vexor_results)
        devrag = _make_devrag_mock(devrag_results)
        retriever = UnifiedRetriever(vexor=vexor, devrag=devrag)

        response = retriever.retrieve_hybrid("some query")

        assert len(response.results) == 1
        assert response.results[0].score == 0.9

    def test_hybrid_sorts_by_score(self):
        """retrieve_hybrid returns results sorted by score descending."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor_results = [
            _make_result("low.py", score=0.4, rank=1),
            _make_result("high.py", score=0.95, rank=2),
        ]
        devrag_results = [
            _make_result("mid.md", score=0.7, rank=1),
        ]
        vexor = _make_vexor_mock(vexor_results)
        devrag = _make_devrag_mock(devrag_results)
        retriever = UnifiedRetriever(vexor=vexor, devrag=devrag)

        response = retriever.retrieve_hybrid("some query")

        scores = [r.score for r in response.results]
        assert scores == sorted(scores, reverse=True)
        assert scores[0] == 0.95

    def test_hybrid_limits_to_top_k(self):
        """retrieve_hybrid returns at most top_k results."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor_results = [_make_result(f"v{i}.py", score=0.9 - i * 0.1, rank=i) for i in range(5)]
        devrag_results = [_make_result(f"d{i}.md", score=0.85 - i * 0.1, rank=i) for i in range(5)]
        vexor = _make_vexor_mock(vexor_results)
        devrag = _make_devrag_mock(devrag_results)
        retriever = UnifiedRetriever(vexor=vexor, devrag=devrag)

        response = retriever.retrieve_hybrid("some query", top_k=3)

        assert len(response.results) == 3

    def test_hybrid_handles_one_backend_failure(self):
        """retrieve_hybrid returns results from the working backend if one fails."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock()
        vexor.search.side_effect = RuntimeError("vexor down")
        devrag_results = [_make_result("rule.md", score=0.8, rank=1)]
        devrag = _make_devrag_mock(devrag_results)
        retriever = UnifiedRetriever(vexor=vexor, devrag=devrag)

        response = retriever.retrieve_hybrid("some query")

        assert len(response.results) == 1
        assert response.results[0].file_path == "rule.md"


# ---------------------------------------------------------------------------
# TestStatus
# ---------------------------------------------------------------------------

class TestStatus:
    def test_status_both_available(self):
        """status() reports both backends available when both report True."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock(available=True)
        devrag = _make_devrag_mock(available=True)
        retriever = UnifiedRetriever(vexor=vexor, devrag=devrag)

        result = retriever.status()

        assert result["vexor_available"] is True
        assert result["devrag_available"] is True

    def test_status_one_unavailable(self):
        """status() reports False for the backend that is unavailable."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock(available=False)
        devrag = _make_devrag_mock(available=True)
        retriever = UnifiedRetriever(vexor=vexor, devrag=devrag)

        result = retriever.status()

        assert result["vexor_available"] is False
        assert result["devrag_available"] is True

    def test_status_includes_governance_stats_when_store_attached(self):
        """status() includes governance_stats when devrag.governance_stats() returns a dict."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock(available=True)
        devrag = _make_devrag_mock(available=True)
        gov_stats = {"total_files": 5, "total_chunks": 12, "by_doc_type": {"rule": 3, "adr": 2}}
        devrag.governance_stats.return_value = gov_stats
        retriever = UnifiedRetriever(vexor=vexor, devrag=devrag)

        result = retriever.status()

        assert "governance_stats" in result
        assert result["governance_stats"] == gov_stats

    def test_status_omits_governance_stats_when_none(self):
        """status() omits governance_stats key when devrag.governance_stats() returns None."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock(available=True)
        devrag = _make_devrag_mock(available=True)
        devrag.governance_stats.return_value = None
        retriever = UnifiedRetriever(vexor=vexor, devrag=devrag)

        result = retriever.status()

        assert "governance_stats" not in result

    def test_status_passes_project_root_to_governance_stats(self):
        """status() calls devrag.governance_stats(project_root=config.project_root)."""
        from stratus.retrieval.config import RetrievalConfig
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock(available=True)
        devrag = _make_devrag_mock(available=True)
        devrag.governance_stats.return_value = None
        config = RetrievalConfig(project_root="/my/project")
        retriever = UnifiedRetriever(vexor=vexor, devrag=devrag, config=config)

        retriever.status()

        devrag.governance_stats.assert_called_once_with(project_root="/my/project")

    def test_status_passes_none_project_root_when_config_has_none(self):
        """status() calls devrag.governance_stats(project_root=None) when config has no root."""
        from stratus.retrieval.config import RetrievalConfig
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock(available=True)
        devrag = _make_devrag_mock(available=True)
        devrag.governance_stats.return_value = None
        config = RetrievalConfig(project_root=None)
        retriever = UnifiedRetriever(vexor=vexor, devrag=devrag, config=config)

        retriever.status()

        devrag.governance_stats.assert_called_once_with(project_root=None)
