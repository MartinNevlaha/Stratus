"""Retrieval routes: search, status, index, index-state, embed-cache stats."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


async def retrieval_search(request: Request) -> JSONResponse:
    """GET /api/retrieval/search?query=...&corpus=...&top_k=10"""
    query = request.query_params.get("query")
    if not query:
        return JSONResponse({"error": "query parameter required"}, status_code=400)

    corpus = request.query_params.get("corpus")
    top_k = int(request.query_params.get("top_k", "10"))

    retriever = request.app.state.retriever
    response = retriever.retrieve(query, corpus=corpus, top_k=top_k)
    return JSONResponse(response.model_dump())


async def retrieval_status(request: Request) -> JSONResponse:
    """GET /api/retrieval/status"""
    retriever = request.app.state.retriever
    return JSONResponse(retriever.status())


async def trigger_index(request: Request) -> JSONResponse:
    """POST /api/retrieval/index"""
    retriever = request.app.state.retriever
    result = retriever._vexor.index()
    return JSONResponse(result)


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
