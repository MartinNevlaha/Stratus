"""Unified retriever: routes queries to Vexor (code) or DevRag (governance)."""

from __future__ import annotations

from stratus.hooks.tool_redirect import classify_query
from stratus.retrieval.config import RetrievalConfig
from stratus.retrieval.devrag import DevRagClient
from stratus.retrieval.models import CorpusType, RetrievalResponse, SearchResult
from stratus.retrieval.vexor import VexorClient

# Query classifications that route to Vexor (code search)
_VEXOR_CLASSIFICATIONS = frozenset({"code", "general"})


class UnifiedRetriever:
    """Routes retrieval requests to the appropriate backend based on corpus or query type."""

    def __init__(
        self,
        vexor: VexorClient | None = None,
        devrag: DevRagClient | None = None,
        config: RetrievalConfig | None = None,
    ) -> None:
        self._config = config or RetrievalConfig()
        self._vexor = vexor or VexorClient()
        self._devrag = devrag or DevRagClient()

    def retrieve(
        self,
        query: str,
        *,
        corpus: str | None = None,
        top_k: int = 10,
    ) -> RetrievalResponse:
        """Route query to the appropriate backend.

        If corpus is explicitly set, use that backend.
        Otherwise auto-classify the query to pick the backend.
        Falls back to the other backend on any exception.
        Returns an empty response if both backends fail.
        """
        if corpus is not None:
            return self._retrieve_with_corpus(query, corpus=corpus, top_k=top_k)

        classification = classify_query(query)
        if classification in _VEXOR_CLASSIFICATIONS:
            return self._try_vexor_then_devrag(query, top_k=top_k)
        return self._try_devrag_then_vexor(query, top_k=top_k)

    def retrieve_hybrid(self, query: str, *, top_k: int = 10) -> RetrievalResponse:
        """Query both backends, merge by score, deduplicate by file_path, return top_k."""
        vexor_results: list[SearchResult] = []
        devrag_results: list[SearchResult] = []

        try:
            response = self._vexor.search(query, top=top_k, path=self._config.project_root)
            vexor_results = response.results
        except Exception:
            pass

        try:
            response = self._devrag.search(query, top_k=top_k)
            devrag_results = response.results
        except Exception:
            pass

        merged = _merge_results(vexor_results + devrag_results, top_k=top_k)
        return RetrievalResponse(
            results=merged,
            corpus=CorpusType.CODE,
            query_time_ms=0.0,
        )

    def status(self) -> dict:
        """Return backend availability and optional governance stats."""
        result: dict = {
            "vexor_available": self._vexor.is_available(),
            "devrag_available": self._devrag.is_available(),
        }
        gov = self._devrag.governance_stats()
        if gov is not None:
            result["governance_stats"] = gov
        return result

    # ------------------------------------------------------------------
    # Private routing helpers
    # ------------------------------------------------------------------

    def _retrieve_with_corpus(
        self, query: str, *, corpus: str, top_k: int
    ) -> RetrievalResponse:
        if corpus == "code":
            return self._try_vexor_then_devrag(query, top_k=top_k)
        return self._try_devrag_then_vexor(query, top_k=top_k)

    def _try_vexor_then_devrag(self, query: str, *, top_k: int) -> RetrievalResponse:
        try:
            return self._vexor.search(query, top=top_k, path=self._config.project_root)
        except Exception:
            pass
        try:
            return self._devrag.search(query, top_k=top_k)
        except Exception:
            pass
        return _empty_response()

    def _try_devrag_then_vexor(self, query: str, *, top_k: int) -> RetrievalResponse:
        try:
            return self._devrag.search(query, top_k=top_k)
        except Exception:
            pass
        try:
            return self._vexor.search(query, top=top_k, path=self._config.project_root)
        except Exception:
            pass
        return _empty_response()


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _empty_response() -> RetrievalResponse:
    return RetrievalResponse(results=[], corpus=CorpusType.CODE, query_time_ms=0.0)


def _merge_results(results: list[SearchResult], *, top_k: int) -> list[SearchResult]:
    """Deduplicate by file_path (keep highest score), sort descending, take top_k."""
    best: dict[str, SearchResult] = {}
    for result in results:
        existing = best.get(result.file_path)
        if existing is None or result.score > existing.score:
            best[result.file_path] = result

    sorted_results = sorted(best.values(), key=lambda r: r.score, reverse=True)
    ranked = [
        r.model_copy(update={"rank": i + 1}) for i, r in enumerate(sorted_results[:top_k])
    ]
    return ranked
