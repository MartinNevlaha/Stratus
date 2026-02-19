"""DevRag client: governance document search via GovernanceStore."""

from __future__ import annotations

import time

from stratus.retrieval.config import DevRagConfig
from stratus.retrieval.governance_store import GovernanceStore
from stratus.retrieval.models import CorpusType, RetrievalResponse, SearchResult


class DevRagClient:
    def __init__(
        self,
        config: DevRagConfig | None = None,
        store: GovernanceStore | None = None,
        project_root: str | None = None,
    ) -> None:
        self._config = config or DevRagConfig()
        self._store = store
        self._project_root = project_root

    def is_available(self) -> bool:
        """True if enabled and a GovernanceStore is attached."""
        return self._config.enabled and self._store is not None

    def search(self, query: str, *, top_k: int = 10, scope: str | None = None) -> RetrievalResponse:
        """Search governance documents via GovernanceStore."""
        if self._store is None:
            return RetrievalResponse(results=[], corpus=CorpusType.GOVERNANCE, query_time_ms=0.0)

        start = time.monotonic()
        doc_type = scope  # scope maps to doc_type filter
        raw = self._store.search(
            query, top_k=top_k, doc_type=doc_type, project_root=self._project_root
        )
        elapsed_ms = (time.monotonic() - start) * 1000
        results = self._parse_search_results(raw)
        return RetrievalResponse(
            results=results,
            corpus=CorpusType.GOVERNANCE,
            query_time_ms=elapsed_ms,
        )

    def list_documents(self) -> list[dict]:
        """List all indexed governance documents."""
        if self._store is None:
            return []
        return self._store.list_documents()

    def governance_stats(self, *, project_root: str | None = None) -> dict | None:
        """Return store stats or None if no store is attached."""
        if self._store is None:
            return None
        return self._store.stats(project_root=project_root or self._project_root)

    def index(self, project_root: str) -> dict:
        """Index governance documents from the project root."""
        if self._store is None:
            return {"status": "error", "message": "no store attached"}
        return self._store.index_project(project_root)

    @staticmethod
    def _parse_search_results(raw_results: list[dict]) -> list[SearchResult]:
        """Convert GovernanceStore search dicts to SearchResult models."""
        results: list[SearchResult] = []
        for rank, item in enumerate(raw_results, start=1):
            results.append(
                SearchResult(
                    file_path=item.get("file_path", ""),
                    score=float(item.get("score", 0.0)),
                    rank=rank,
                    excerpt=item.get("content", ""),
                    language=None,
                    line_start=None,
                    line_end=None,
                    corpus=CorpusType.GOVERNANCE,
                    chunk_index=item.get("chunk_index"),
                    title=item.get("title") or None,
                    doc_type=item.get("doc_type") or None,
                )
            )
        return results
