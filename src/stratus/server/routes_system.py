"""System routes: health, version, stats."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from stratus import __version__ as VERSION


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


async def version(request: Request) -> JSONResponse:
    return JSONResponse({"version": VERSION})


async def stats(request: Request) -> JSONResponse:
    db = request.app.state.db
    return JSONResponse(db.get_stats())


routes = [
    Route("/health", health),
    Route("/api/version", version),
    Route("/api/stats", stats),
]
