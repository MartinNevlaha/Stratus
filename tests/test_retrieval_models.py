"""Tests for retrieval Pydantic models."""

from stratus.retrieval.models import (
    CorpusType,
    IndexStatus,
    RetrievalResponse,
    SearchResult,
)


class TestCorpusType:
    def test_corpus_type_code(self):
        assert CorpusType.CODE == "code"

    def test_corpus_type_governance(self):
        assert CorpusType.GOVERNANCE == "governance"

    def test_corpus_type_is_str(self):
        assert isinstance(CorpusType.CODE, str)


class TestSearchResult:
    def test_search_result_minimal(self):
        result = SearchResult(file_path="src/main.py", score=0.95, rank=1, excerpt="def main():")
        assert result.file_path == "src/main.py"
        assert result.score == 0.95
        assert result.rank == 1
        assert result.excerpt == "def main():"

    def test_search_result_all_fields(self):
        result = SearchResult(
            file_path="src/auth.py",
            score=0.88,
            rank=2,
            excerpt="class Auth:",
            language="python",
            line_start=10,
            line_end=20,
            corpus=CorpusType.CODE,
            chunk_index=0,
        )
        assert result.language == "python"
        assert result.line_start == 10
        assert result.line_end == 20
        assert result.corpus == CorpusType.CODE
        assert result.chunk_index == 0

    def test_search_result_defaults(self):
        result = SearchResult(file_path="f.py", score=0.5, rank=1, excerpt="x")
        assert result.language is None
        assert result.line_start is None
        assert result.line_end is None
        assert result.corpus is None
        assert result.chunk_index is None

    def test_search_result_serialization(self):
        result = SearchResult(file_path="f.py", score=0.5, rank=1, excerpt="x")
        data = result.model_dump()
        assert data["file_path"] == "f.py"
        assert data["score"] == 0.5


class TestRetrievalResponse:
    def test_retrieval_response_empty(self):
        resp = RetrievalResponse(results=[], corpus=CorpusType.CODE, query_time_ms=42)
        assert resp.results == []
        assert resp.corpus == CorpusType.CODE
        assert resp.query_time_ms == 42
        assert resp.total_indexed is None

    def test_retrieval_response_with_results(self):
        results = [
            SearchResult(file_path="a.py", score=0.9, rank=1, excerpt="hello"),
            SearchResult(file_path="b.py", score=0.8, rank=2, excerpt="world"),
        ]
        resp = RetrievalResponse(
            results=results, corpus=CorpusType.GOVERNANCE, query_time_ms=15, total_indexed=100
        )
        assert len(resp.results) == 2
        assert resp.total_indexed == 100

    def test_retrieval_response_serialization(self):
        resp = RetrievalResponse(results=[], corpus=CorpusType.CODE, query_time_ms=5)
        data = resp.model_dump()
        assert "results" in data
        assert "corpus" in data
        assert "query_time_ms" in data


class TestIndexStatus:
    def test_index_status_defaults(self):
        status = IndexStatus()
        assert status.last_indexed_commit is None
        assert status.last_indexed_at is None
        assert status.total_files == 0
        assert status.model is None
        assert status.stale is True

    def test_index_status_all_fields(self):
        status = IndexStatus(
            last_indexed_commit="abc123",
            last_indexed_at="2026-02-17T10:00:00Z",
            total_files=500,
            model="nomic-embed-text-v1.5",
            stale=False,
        )
        assert status.last_indexed_commit == "abc123"
        assert status.total_files == 500
        assert status.stale is False
