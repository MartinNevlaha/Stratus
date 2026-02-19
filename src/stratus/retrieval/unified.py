"""Unified retriever: routes queries to Vexor (code) or GovernanceStore (governance)."""

from __future__ import annotations

import time

from stratus.hooks.tool_redirect import classify_query
from stratus.retrieval.config import RetrievalConfig
from stratus.retrieval.models import CorpusType, RetrievalResponse, SearchResult
from stratus.retrieval.vexor import VexorClient

# Query classifications that route to Vexor (code search)
_VEXOR_CLASSIFICATIONS = frozenset({"code", "general"})


class UnifiedRetriever:
    """Routes retrieval requests to the appropriate backend based on corpus or query type."""

    def __init__(
        self,
        vexor: VexorClient | None = None,
        governance: object | None = None,
        config: RetrievalConfig | None = None,
    ) -> None:
        self._config = config or RetrievalConfig()
        self._vexor = vexor or VexorClient()
        self._governance = governance  # GovernanceStore instance or None

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
            return self._try_vexor_then_governance(query, top_k=top_k)
        return self._try_governance_then_vexor(query, top_k=top_k)

    def retrieve_hybrid(self, query: str, *, top_k: int = 10) -> RetrievalResponse:
        """Query both backends, merge by score, deduplicate by file_path, return top_k."""
        vexor_results: list[SearchResult] = []
        governance_results: list[SearchResult] = []

        try:
            response = self._vexor.search(query, top=top_k, path=self._config.project_root)
            vexor_results = response.results
        except Exception:
            pass

        if self._governance is not None:
            try:
                raw = self._governance.search(  # type: ignore[union-attr]
                    query, top_k=top_k, project_root=self._config.project_root
                )
                governance_results = _parse_governance_results(raw)
            except Exception:
                pass

        merged = _merge_results(vexor_results + governance_results, top_k=top_k)
        return RetrievalResponse(
            results=merged,
            corpus=CorpusType.CODE,
            query_time_ms=0.0,
        )

    def status(self) -> dict:
        """Return backend availability and optional governance stats."""
        result: dict = {
            "vexor_available": self._vexor.is_available(),
            "governance_available": self._governance is not None,
        }
        if self._governance is not None:
            gov = self._governance.stats(  # type: ignore[union-attr]
                project_root=self._config.project_root
            )
            if gov is not None:
                result["governance_stats"] = gov
        return result

    def index_governance(self, project_root: str) -> dict:
        """Index governance documents from project_root via GovernanceStore.

        Returns {"status": "unavailable"} if no governance store is attached.
        """
        if self._governance is None:
            return {"status": "unavailable"}
        return self._governance.index_project(project_root)  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # Private routing helpers
    # ------------------------------------------------------------------

    def _retrieve_with_corpus(
        self, query: str, *, corpus: str, top_k: int
    ) -> RetrievalResponse:
        if corpus == "code":
            return self._try_vexor_then_governance(query, top_k=top_k)
        return self._try_governance_then_vexor(query, top_k=top_k)

    def _try_vexor_then_governance(self, query: str, *, top_k: int) -> RetrievalResponse:
        try:
            return self._vexor.search(query, top=top_k, path=self._config.project_root)
        except Exception:
            pass
        if self._governance is not None:
            try:
                start = time.monotonic()
                raw = self._governance.search(  # type: ignore[union-attr]
                    query, top_k=top_k, project_root=self._config.project_root
                )
                elapsed_ms = (time.monotonic() - start) * 1000
                return RetrievalResponse(
                    results=_parse_governance_results(raw),
                    corpus=CorpusType.GOVERNANCE,
                    query_time_ms=elapsed_ms,
                )
            except Exception:
                pass
        return _empty_response()

    def _try_governance_then_vexor(self, query: str, *, top_k: int) -> RetrievalResponse:
        if self._governance is not None:
            try:
                start = time.monotonic()
                raw = self._governance.search(  # type: ignore[union-attr]
                    query, top_k=top_k, project_root=self._config.project_root
                )
                elapsed_ms = (time.monotonic() - start) * 1000
                return RetrievalResponse(
                    results=_parse_governance_results(raw),
                    corpus=CorpusType.GOVERNANCE,
                    query_time_ms=elapsed_ms,
                )
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


def _parse_governance_results(raw_results: list[dict]) -> list[SearchResult]:
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
