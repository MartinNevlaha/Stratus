"""Retrieval routes: search, status, index, index-state, embed-cache stats."""

from __future__ import annotations

import asyncio
import json as _json
import threading
from pathlib import Path

from starlette.background import BackgroundTasks
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


async def retrieval_search(request: Request) -> JSONResponse:
    """GET /api/retrieval/search?query=...&corpus=...&top_k=10"""
    query = request.query_params.get("query")
    if not query:
        return JSONResponse({"error": "query parameter required"}, status_code=400)

    corpus = request.query_params.get("corpus")
    try:
        top_k = int(request.query_params.get("top_k", "10"))
    except ValueError:
        return JSONResponse({"error": "top_k must be an integer"}, status_code=400)
    top_k = min(max(top_k, 1), 100)

    retriever = request.app.state.retriever
    response = await asyncio.to_thread(retriever.retrieve, query, corpus=corpus, top_k=top_k)
    return JSONResponse(response.model_dump())


async def retrieval_status(request: Request) -> JSONResponse:
    """GET /api/retrieval/status"""
    from stratus.retrieval.index_state import read_index_state
    from stratus.session.config import get_data_dir

    retriever = request.app.state.retriever
    data = await asyncio.to_thread(retriever.status)
    state = read_index_state(get_data_dir())
    state_dict = state.model_dump()
    # Merge live vexor stats (total_files, model, last_indexed_at) into state
    live = await asyncio.to_thread(retriever._vexor.show, path=retriever._config.project_root)
    state_dict.update({k: v for k, v in live.items() if v is not None})
    data["index_state"] = state_dict
    return JSONResponse(data)


def _do_index(retriever: object, data_dir: Path, lock: threading.Lock) -> None:
    """Run vexor index and persist updated index state. Best-effort. Skips if already running."""
    if not lock.acquire(blocking=False):
        return  # Already indexing, skip
    try:
        try:
            from stratus.retrieval.index_state import get_current_commit, write_index_state
            from stratus.retrieval.models import IndexStatus

            retriever._vexor.index()  # type: ignore[union-attr]
            commit = get_current_commit(Path.cwd())
            write_index_state(data_dir, IndexStatus(stale=False, last_indexed_commit=commit))
        except Exception:
            pass

        try:
            retriever.index_governance(str(Path.cwd()))  # type: ignore[union-attr]
        except Exception:
            pass
    finally:
        lock.release()


async def trigger_index(request: Request) -> JSONResponse:
    """POST /api/retrieval/index"""
    from stratus.session.config import get_data_dir

    # Validate project_root if provided
    try:
        body = await request.body()
        body_data = _json.loads(body) if body else {}
    except Exception:
        body_data = {}

    requested_root = body_data.get("project_root")
    if requested_root:
        config = getattr(request.app.state.retriever, "_config", None)
        if config and config.project_root:
            if str(Path(requested_root).resolve()) != str(Path(config.project_root).resolve()):
                return JSONResponse(
                    {"status": "skipped", "reason": "project_root mismatch"},
                    status_code=200,
                )

    retriever = request.app.state.retriever
    data_dir = get_data_dir()
    lock = request.app.state.index_lock

    tasks = BackgroundTasks()
    tasks.add_task(_do_index, retriever, data_dir, lock)
    return JSONResponse({"status": "indexing started"}, status_code=202, background=tasks)


async def index_state(request: Request) -> JSONResponse:
    """GET /api/retrieval/index-state"""
    from stratus.retrieval.index_state import read_index_state
    from stratus.session.config import get_data_dir

    status = read_index_state(get_data_dir())
    return JSONResponse(status.model_dump())


async def embed_cache_stats(request: Request) -> JSONResponse:
    """GET /api/retrieval/embed-cache/stats"""
    embed_cache = request.app.state.embed_cache
    return JSONResponse(embed_cache.stats())


routes = [
    Route("/api/retrieval/search", retrieval_search),
    Route("/api/retrieval/status", retrieval_status),
    Route("/api/retrieval/index", trigger_index, methods=["POST"]),
    Route("/api/retrieval/index-state", index_state),
    Route("/api/retrieval/embed-cache/stats", embed_cache_stats),
]
