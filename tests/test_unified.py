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


def _make_governance_mock(available: bool = True) -> MagicMock:
    """Mock for GovernanceStore used directly by UnifiedRetriever."""
    mock = MagicMock()
    # is_available is determined by whether governance is not None in UnifiedRetriever
    # but we also need a way to simulate "no store" — pass None instead of mock
    mock.search.return_value = []
    mock.stats.return_value = None
    return mock


# ---------------------------------------------------------------------------
# TestRetrieve
# ---------------------------------------------------------------------------

class TestRetrieve:
    def test_retrieve_explicit_code_corpus(self):
        """corpus='code' routes to VexorClient.search."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock([_make_result("src/main.py", score=0.95)])
        governance = _make_governance_mock()
        retriever = UnifiedRetriever(vexor=vexor, governance=governance)

        response = retriever.retrieve("find the main function", corpus="code", top_k=5)

        vexor.search.assert_called_once_with("find the main function", top=5, path=None)
        governance.search.assert_not_called()
        assert response.corpus == CorpusType.CODE
        assert len(response.results) == 1

    def test_retrieve_explicit_governance_corpus(self):
        """corpus='governance' routes to GovernanceStore.search."""
        from stratus.retrieval.unified import UnifiedRetriever

        gov_raw = [
            {"file_path": "policy.md", "score": 0.88, "content": "text",
             "chunk_index": 0, "title": None, "doc_type": None}
        ]
        vexor = _make_vexor_mock()
        governance = _make_governance_mock()
        governance.search.return_value = gov_raw
        retriever = UnifiedRetriever(vexor=vexor, governance=governance)

        response = retriever.retrieve("naming convention", corpus="governance", top_k=3)

        governance.search.assert_called_once_with("naming convention", top_k=3, project_root=None)
        vexor.search.assert_not_called()
        assert response.corpus == CorpusType.GOVERNANCE
        assert len(response.results) == 1

    def test_retrieve_auto_classifies_code_query(self):
        """'where is the function' → classify_query → 'code' → Vexor."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock([_make_result()])
        governance = _make_governance_mock()
        retriever = UnifiedRetriever(vexor=vexor, governance=governance)

        response = retriever.retrieve("where is the function defined")

        vexor.search.assert_called_once()
        governance.search.assert_not_called()
        assert response.corpus == CorpusType.CODE

    def test_retrieve_auto_classifies_rule_query(self):
        """'what is the naming convention' → classify_query → 'rule' → GovernanceStore."""
        from stratus.retrieval.unified import UnifiedRetriever

        gov_raw = [
            {"file_path": "rules.md", "score": 0.7, "content": "text",
             "chunk_index": 0, "title": None, "doc_type": None}
        ]
        vexor = _make_vexor_mock()
        governance = _make_governance_mock()
        governance.search.return_value = gov_raw
        retriever = UnifiedRetriever(vexor=vexor, governance=governance)

        response = retriever.retrieve("what is the naming convention")

        governance.search.assert_called_once()
        vexor.search.assert_not_called()
        assert response.corpus == CorpusType.GOVERNANCE

    def test_retrieve_auto_classifies_general_query(self):
        """'python 3.12' → classify_query → 'general' → Vexor."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock([_make_result()])
        governance = _make_governance_mock()
        retriever = UnifiedRetriever(vexor=vexor, governance=governance)

        retriever.retrieve("python 3.12")

        vexor.search.assert_called_once()
        governance.search.assert_not_called()

    def test_retrieve_fallback_when_vexor_fails(self):
        """If Vexor raises, falls back to GovernanceStore."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock()
        vexor.search.side_effect = RuntimeError("vexor unavailable")
        gov_raw = [
            {"file_path": "fallback.py", "score": 0.5, "content": "text",
             "chunk_index": 0, "title": None, "doc_type": None}
        ]
        governance = _make_governance_mock()
        governance.search.return_value = gov_raw
        retriever = UnifiedRetriever(vexor=vexor, governance=governance)

        response = retriever.retrieve("find the main function", corpus="code")

        governance.search.assert_called_once()
        assert len(response.results) == 1
        assert response.results[0].file_path == "fallback.py"

    def test_retrieve_fallback_when_governance_fails(self):
        """If GovernanceStore raises, falls back to Vexor."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock([_make_result("vexor_result.py", score=0.8)])
        governance = _make_governance_mock()
        governance.search.side_effect = RuntimeError("governance unavailable")
        retriever = UnifiedRetriever(vexor=vexor, governance=governance)

        response = retriever.retrieve("naming convention", corpus="governance")

        vexor.search.assert_called_once()
        assert len(response.results) == 1
        assert response.results[0].file_path == "vexor_result.py"

    def test_retrieve_returns_empty_when_both_fail(self):
        """If both backends raise, returns empty RetrievalResponse."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock()
        vexor.search.side_effect = RuntimeError("vexor unavailable")
        governance = _make_governance_mock()
        governance.search.side_effect = RuntimeError("governance unavailable")
        retriever = UnifiedRetriever(vexor=vexor, governance=governance)

        response = retriever.retrieve("find the main function", corpus="code")

        assert response.results == []


# ---------------------------------------------------------------------------
# TestRetrieveHybrid
# ---------------------------------------------------------------------------

class TestRetrieveHybrid:
    def test_hybrid_merges_both_backends(self):
        """retrieve_hybrid queries both Vexor and GovernanceStore and combines results."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor_results = [_make_result("a.py", score=0.9, rank=1)]
        gov_raw = [
            {"file_path": "b.md", "score": 0.8, "content": "text",
             "chunk_index": 0, "title": None, "doc_type": None}
        ]
        vexor = _make_vexor_mock(vexor_results)
        governance = _make_governance_mock()
        governance.search.return_value = gov_raw
        retriever = UnifiedRetriever(vexor=vexor, governance=governance)

        response = retriever.retrieve_hybrid("some query")

        vexor.search.assert_called_once()
        governance.search.assert_called_once()
        assert len(response.results) == 2

    def test_hybrid_deduplicates_by_file_path(self):
        """retrieve_hybrid keeps highest score when same file_path appears in both."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor_results = [_make_result("shared.py", score=0.9, rank=1)]
        gov_raw = [
            {"file_path": "shared.py", "score": 0.7, "content": "text",
             "chunk_index": 0, "title": None, "doc_type": None}
        ]
        vexor = _make_vexor_mock(vexor_results)
        governance = _make_governance_mock()
        governance.search.return_value = gov_raw
        retriever = UnifiedRetriever(vexor=vexor, governance=governance)

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
        gov_raw = [
            {"file_path": "mid.md", "score": 0.7, "content": "text",
             "chunk_index": 0, "title": None, "doc_type": None}
        ]
        vexor = _make_vexor_mock(vexor_results)
        governance = _make_governance_mock()
        governance.search.return_value = gov_raw
        retriever = UnifiedRetriever(vexor=vexor, governance=governance)

        response = retriever.retrieve_hybrid("some query")

        scores = [r.score for r in response.results]
        assert scores == sorted(scores, reverse=True)
        assert scores[0] == 0.95

    def test_hybrid_limits_to_top_k(self):
        """retrieve_hybrid returns at most top_k results."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor_results = [_make_result(f"v{i}.py", score=0.9 - i * 0.1, rank=i) for i in range(5)]
        gov_raw = [
            {"file_path": f"d{i}.md", "score": 0.85 - i * 0.1, "content": "text",
             "chunk_index": 0, "title": None, "doc_type": None}
            for i in range(5)
        ]
        vexor = _make_vexor_mock(vexor_results)
        governance = _make_governance_mock()
        governance.search.return_value = gov_raw
        retriever = UnifiedRetriever(vexor=vexor, governance=governance)

        response = retriever.retrieve_hybrid("some query", top_k=3)

        assert len(response.results) == 3

    def test_hybrid_handles_one_backend_failure(self):
        """retrieve_hybrid returns results from the working backend if one fails."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock()
        vexor.search.side_effect = RuntimeError("vexor down")
        gov_raw = [
            {"file_path": "rule.md", "score": 0.8, "content": "text",
             "chunk_index": 0, "title": None, "doc_type": None}
        ]
        governance = _make_governance_mock()
        governance.search.return_value = gov_raw
        retriever = UnifiedRetriever(vexor=vexor, governance=governance)

        response = retriever.retrieve_hybrid("some query")

        assert len(response.results) == 1
        assert response.results[0].file_path == "rule.md"


# ---------------------------------------------------------------------------
# TestStatus
# ---------------------------------------------------------------------------

class TestStatus:
    def test_status_both_available(self):
        """status() reports vexor and governance available when both present."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock(available=True)
        governance = _make_governance_mock()
        retriever = UnifiedRetriever(vexor=vexor, governance=governance)

        result = retriever.status()

        assert result["vexor_available"] is True
        assert result["governance_available"] is True

    def test_status_governance_unavailable_when_none(self):
        """status() reports governance_available=False when governance is None."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock(available=True)
        retriever = UnifiedRetriever(vexor=vexor, governance=None)

        result = retriever.status()

        assert result["vexor_available"] is True
        assert result["governance_available"] is False

    def test_status_includes_governance_stats_when_store_attached(self):
        """status() includes governance_stats when governance.stats() returns a dict."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock(available=True)
        governance = _make_governance_mock()
        gov_stats = {"total_files": 5, "total_chunks": 12, "by_doc_type": {"rule": 3, "adr": 2}}
        governance.stats.return_value = gov_stats
        retriever = UnifiedRetriever(vexor=vexor, governance=governance)

        result = retriever.status()

        assert "governance_stats" in result
        assert result["governance_stats"] == gov_stats

    def test_status_omits_governance_stats_when_none(self):
        """status() omits governance_stats key when governance.stats() returns None."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock(available=True)
        governance = _make_governance_mock()
        governance.stats.return_value = None
        retriever = UnifiedRetriever(vexor=vexor, governance=governance)

        result = retriever.status()

        assert "governance_stats" not in result

    def test_status_passes_project_root_to_governance_stats(self):
        """status() calls governance.stats(project_root=config.project_root)."""
        from stratus.retrieval.config import RetrievalConfig
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock(available=True)
        governance = _make_governance_mock()
        governance.stats.return_value = None
        config = RetrievalConfig(project_root="/my/project")
        retriever = UnifiedRetriever(vexor=vexor, governance=governance, config=config)

        retriever.status()

        governance.stats.assert_called_once_with(project_root="/my/project")

    def test_status_passes_none_project_root_when_config_has_none(self):
        """status() calls governance.stats(project_root=None) when config has no root."""
        from stratus.retrieval.config import RetrievalConfig
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock(available=True)
        governance = _make_governance_mock()
        governance.stats.return_value = None
        config = RetrievalConfig(project_root=None)
        retriever = UnifiedRetriever(vexor=vexor, governance=governance, config=config)

        retriever.status()

        governance.stats.assert_called_once_with(project_root=None)


# ---------------------------------------------------------------------------
# TestIndexGovernance
# ---------------------------------------------------------------------------


class TestIndexGovernance:
    def test_index_governance_delegates_to_governance_store(self):
        """index_governance() calls governance.index_project() and returns its result."""
        from stratus.retrieval.unified import UnifiedRetriever

        governance = _make_governance_mock()
        governance.index_project.return_value = {"files_indexed": 5, "chunks_indexed": 12}
        vexor = _make_vexor_mock(available=True)
        retriever = UnifiedRetriever(vexor=vexor, governance=governance)

        result = retriever.index_governance("/some/project")

        governance.index_project.assert_called_once_with("/some/project")
        assert result == {"files_indexed": 5, "chunks_indexed": 12}

    def test_index_governance_returns_unavailable_when_governance_none(self):
        """index_governance() returns unavailable dict when governance is None."""
        from stratus.retrieval.unified import UnifiedRetriever

        vexor = _make_vexor_mock(available=True)
        retriever = UnifiedRetriever(vexor=vexor, governance=None)

        result = retriever.index_governance("/some/project")

        assert result == {"status": "unavailable"}


# ---------------------------------------------------------------------------
# TestParseGovernanceResults (module-level helper)
# ---------------------------------------------------------------------------


class TestParseGovernanceResults:
    def test_parse_governance_results_basic(self) -> None:
        from stratus.retrieval.unified import _parse_governance_results

        raw = [
            {"file_path": "docs/api.md", "content": "API documentation...", "score": -0.92},
            {"file_path": "docs/auth.md", "content": "Auth docs", "score": -0.75},
        ]
        results = _parse_governance_results(raw)
        assert len(results) == 2
        assert all(isinstance(r, SearchResult) for r in results)
        assert results[0].file_path == "docs/api.md"
        assert results[0].score == -0.92
        assert results[0].rank == 1
        assert results[0].excerpt == "API documentation..."
        assert results[0].corpus == CorpusType.GOVERNANCE
        assert results[1].rank == 2

    def test_parse_governance_results_includes_title_and_doc_type(self) -> None:
        from stratus.retrieval.unified import _parse_governance_results

        raw = [
            {
                "file_path": ".claude/rules/testing.md",
                "title": "Testing",
                "content": "Always write tests first",
                "doc_type": "rule",
                "score": -0.85,
                "chunk_index": 0,
            }
        ]
        results = _parse_governance_results(raw)
        assert results[0].title == "Testing"
        assert results[0].doc_type == "rule"

    def test_parse_governance_results_empty(self) -> None:
        from stratus.retrieval.unified import _parse_governance_results

        results = _parse_governance_results([])
        assert results == []
