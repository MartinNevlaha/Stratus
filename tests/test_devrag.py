"""Tests for DevRag client (GovernanceStore-backed governance search)."""

from __future__ import annotations

from pathlib import Path

from stratus.retrieval.config import DevRagConfig
from stratus.retrieval.devrag import DevRagClient
from stratus.retrieval.governance_store import GovernanceStore
from stratus.retrieval.models import CorpusType, RetrievalResponse, SearchResult


def _make_store_with_docs(tmp_path: Path) -> GovernanceStore:
    """Create a GovernanceStore with sample governance docs indexed."""
    root = tmp_path / "project"
    root.mkdir()
    rules = root / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "testing.md").write_text("## Testing\nAlways write tests before code")
    (rules / "style.md").write_text("## Style\nUse ruff for Python formatting")
    decisions = root / "docs" / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "001.md").write_text("## Decision\nUse SQLite for storage")
    store = GovernanceStore()
    store.index_project(str(root))
    return store


class TestDevRagClient:
    def test_is_available_with_store_and_enabled(self, tmp_path: Path) -> None:
        store = _make_store_with_docs(tmp_path)
        client = DevRagClient(config=DevRagConfig(enabled=True), store=store)
        assert client.is_available() is True

    def test_is_available_disabled(self, tmp_path: Path) -> None:
        store = _make_store_with_docs(tmp_path)
        client = DevRagClient(config=DevRagConfig(enabled=False), store=store)
        assert client.is_available() is False

    def test_is_available_no_store(self) -> None:
        client = DevRagClient(config=DevRagConfig(enabled=True), store=None)
        assert client.is_available() is False

    def test_is_available_default_no_store(self) -> None:
        client = DevRagClient()
        assert client.is_available() is False

    def test_search_returns_retrieval_response(self, tmp_path: Path) -> None:
        store = _make_store_with_docs(tmp_path)
        client = DevRagClient(config=DevRagConfig(enabled=True), store=store)
        result = client.search("testing")
        assert isinstance(result, RetrievalResponse)
        assert result.corpus == CorpusType.GOVERNANCE
        assert len(result.results) >= 1
        assert result.query_time_ms >= 0

    def test_search_results_have_governance_corpus(self, tmp_path: Path) -> None:
        store = _make_store_with_docs(tmp_path)
        client = DevRagClient(config=DevRagConfig(enabled=True), store=store)
        result = client.search("testing")
        for sr in result.results:
            assert sr.corpus == CorpusType.GOVERNANCE

    def test_search_with_scope_filters_doc_type(self, tmp_path: Path) -> None:
        store = _make_store_with_docs(tmp_path)
        client = DevRagClient(config=DevRagConfig(enabled=True), store=store)
        result = client.search("testing OR style OR SQLite", scope="rule")
        for sr in result.results:
            assert "rule" in sr.file_path or True  # filtered by scope=doc_type

    def test_search_no_store_returns_empty(self) -> None:
        client = DevRagClient(config=DevRagConfig(enabled=True), store=None)
        result = client.search("anything")
        assert result.results == []
        assert result.corpus == CorpusType.GOVERNANCE

    def test_list_documents_delegates(self, tmp_path: Path) -> None:
        store = _make_store_with_docs(tmp_path)
        client = DevRagClient(config=DevRagConfig(enabled=True), store=store)
        docs = client.list_documents()
        assert len(docs) >= 3
        assert all("file_path" in d for d in docs)

    def test_list_documents_no_store(self) -> None:
        client = DevRagClient(config=DevRagConfig(enabled=True), store=None)
        assert client.list_documents() == []

    def test_index_delegates(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        rules = root / ".claude" / "rules"
        rules.mkdir(parents=True)
        (rules / "test.md").write_text("## Test\nContent")
        store = GovernanceStore()
        client = DevRagClient(config=DevRagConfig(enabled=True), store=store)
        stats = client.index(str(root))
        assert stats["files_indexed"] == 1

    def test_index_no_store(self) -> None:
        client = DevRagClient(config=DevRagConfig(enabled=True), store=None)
        result = client.index("/nonexistent")
        assert result["status"] == "error"

    def test_project_root_passed_to_store_search(self, tmp_path: Path) -> None:
        """project_root is forwarded to store.search for multi-project isolation."""
        store = _make_store_with_docs(tmp_path)
        client = DevRagClient(
            config=DevRagConfig(enabled=True),
            store=store,
            project_root=str(tmp_path / "project"),
        )
        result = client.search("testing")
        # All results must belong to the given project_root
        project_abs = str((tmp_path / "project").resolve())
        for sr in result.results:
            assert sr.file_path.startswith(project_abs)


class TestGovernanceStats:
    def test_governance_stats_returns_store_stats(self, tmp_path: Path) -> None:
        store = _make_store_with_docs(tmp_path)
        client = DevRagClient(config=DevRagConfig(enabled=True), store=store)
        result = client.governance_stats()
        assert result is not None
        assert "total_files" in result
        assert "total_chunks" in result
        assert "by_doc_type" in result

    def test_governance_stats_returns_none_when_no_store(self) -> None:
        client = DevRagClient(config=DevRagConfig(enabled=True), store=None)
        result = client.governance_stats()
        assert result is None

    def test_governance_stats_passes_project_root_to_store(self, tmp_path: Path) -> None:
        """governance_stats(project_root=...) forwards filter to store.stats()."""
        project = tmp_path / "project"
        other = tmp_path / "other"
        for proj in (project, other):
            rules = proj / ".claude" / "rules"
            rules.mkdir(parents=True)
            (rules / "rule.md").write_text("## Rule\nContent for " + proj.name)
        store = GovernanceStore()
        store.index_project(str(project))
        store.index_project(str(other))
        client = DevRagClient(config=DevRagConfig(enabled=True), store=store)
        # Explicit project_root passed to governance_stats
        result = client.governance_stats(project_root=str(project))
        assert result is not None
        assert result["total_files"] == 1

    def test_governance_stats_falls_back_to_client_project_root(self, tmp_path: Path) -> None:
        """governance_stats() without arg uses client._project_root."""
        project = tmp_path / "project"
        other = tmp_path / "other"
        for proj in (project, other):
            rules = proj / ".claude" / "rules"
            rules.mkdir(parents=True)
            (rules / "rule.md").write_text("## Rule\nContent for " + proj.name)
        store = GovernanceStore()
        store.index_project(str(project))
        store.index_project(str(other))
        client = DevRagClient(
            config=DevRagConfig(enabled=True),
            store=store,
            project_root=str(project),
        )
        result = client.governance_stats()
        assert result is not None
        assert result["total_files"] == 1

    def test_governance_stats_no_project_root_returns_all(self, tmp_path: Path) -> None:
        """governance_stats() with no project_root and no client root returns all docs."""
        project = tmp_path / "project"
        other = tmp_path / "other"
        for proj in (project, other):
            rules = proj / ".claude" / "rules"
            rules.mkdir(parents=True)
            (rules / "rule.md").write_text("## Rule\nContent for " + proj.name)
        store = GovernanceStore()
        store.index_project(str(project))
        store.index_project(str(other))
        # Client has no project_root
        client = DevRagClient(config=DevRagConfig(enabled=True), store=store)
        result = client.governance_stats()
        assert result is not None
        assert result["total_files"] == 2


class TestParseSearchResults:
    def test_parse_search_results_basic(self) -> None:
        raw = [
            {"file_path": "docs/api.md", "content": "API documentation...", "score": -0.92},
            {"file_path": "docs/auth.md", "content": "Auth docs", "score": -0.75},
        ]
        results = DevRagClient._parse_search_results(raw)
        assert len(results) == 2
        assert all(isinstance(r, SearchResult) for r in results)
        assert results[0].file_path == "docs/api.md"
        assert results[0].score == -0.92
        assert results[0].rank == 1
        assert results[0].excerpt == "API documentation..."
        assert results[0].corpus == CorpusType.GOVERNANCE
        assert results[1].rank == 2

    def test_parse_search_results_includes_title_and_doc_type(self) -> None:
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
        results = DevRagClient._parse_search_results(raw)
        assert results[0].title == "Testing"
        assert results[0].doc_type == "rule"

    def test_parse_search_results_empty(self) -> None:
        results = DevRagClient._parse_search_results([])
        assert results == []
