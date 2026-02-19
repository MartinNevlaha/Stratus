"""Memory routes: save, search, timeline, observations."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from stratus.memory.models import MemoryEvent


class SaveMemoryRequest(BaseModel):
    text: str
    title: str | None = None
    type: str = "discovery"
    actor: str = "agent"
    scope: str = "repo"
    tags: list[str] = Field(default_factory=list)
    refs: dict = Field(default_factory=dict)
    importance: float = 0.5
    project: str | None = None
    session_id: str | None = None
    dedupe_key: str | None = None
    ttl: str | None = None
    ts: str | None = None


async def save_memory(request: Request) -> JSONResponse:
    try:
        body = await request.json()
        req = SaveMemoryRequest.model_validate(body)
    except (json.JSONDecodeError, ValueError):
        return JSONResponse({"error": "Invalid request: 'text' is required"}, status_code=422)

    event_kwargs = req.model_dump(exclude_none=True)
    event = MemoryEvent(**event_kwargs)

    db = request.app.state.db
    event_id = db.save_event(event)
    return JSONResponse({"id": event_id})


async def search(request: Request) -> JSONResponse:
    query = request.query_params.get("query")
    if not query:
        return JSONResponse({"error": "query parameter required"}, status_code=400)

    db = request.app.state.db
    kwargs: dict = {}
    for key in ("type", "scope", "project", "date_start", "date_end"):
        val = request.query_params.get(key)
        if val:
            kwargs[key] = val

    try:
        limit = int(request.query_params.get("limit", "20"))
        offset = int(request.query_params.get("offset", "0"))
    except ValueError:
        return JSONResponse({"error": "limit and offset must be integers"}, status_code=400)
    limit = min(max(limit, 0), 1000)
    offset = max(offset, 0)

    results = db.search(query, limit=limit, offset=offset, **kwargs)
    return JSONResponse(
        {
            "results": [r.model_dump() for r in results],
            "count": len(results),
        }
    )


async def timeline(request: Request) -> JSONResponse:
    anchor_id_str = request.query_params.get("anchor_id")
    if not anchor_id_str:
        return JSONResponse({"error": "anchor_id parameter required"}, status_code=400)

    try:
        anchor_id = int(anchor_id_str)
        depth_before = int(request.query_params.get("depth_before", "10"))
        depth_after = int(request.query_params.get("depth_after", "10"))
    except ValueError:
        return JSONResponse(
            {"error": "anchor_id, depth_before, depth_after must be integers"},
            status_code=400,
        )
    depth_before = min(max(depth_before, 0), 100)
    depth_after = min(max(depth_after, 0), 100)
    project = request.query_params.get("project")

    db = request.app.state.db
    events = db.timeline(
        anchor_id=anchor_id,
        depth_before=depth_before,
        depth_after=depth_after,
        project=project,
    )
    return JSONResponse({"events": [e.model_dump() for e in events]})


async def observations(request: Request) -> JSONResponse:
    ids_str = request.query_params.get("ids", "")
    if not ids_str:
        return JSONResponse({"error": "ids parameter required"}, status_code=400)

    try:
        ids = [int(x.strip()) for x in ids_str.split(",") if x.strip()]
    except ValueError:
        return JSONResponse({"error": "ids must be comma-separated integers"}, status_code=400)
    db = request.app.state.db
    events = db.get_events(ids)
    return JSONResponse({"events": [e.model_dump() for e in events]})


async def observations_batch(request: Request) -> JSONResponse:
    body = await request.json()
    ids = body.get("ids")
    if not ids:
        return JSONResponse({"error": "ids field required"}, status_code=400)

    db = request.app.state.db
    events = db.get_events(ids)
    return JSONResponse({"events": [e.model_dump() for e in events]})


routes = [
    Route("/api/memory/save", save_memory, methods=["POST"]),
    Route("/api/search", search),
    Route("/api/timeline", timeline),
    Route("/api/observations", observations),
    Route("/api/observations/batch", observations_batch, methods=["POST"]),
]
