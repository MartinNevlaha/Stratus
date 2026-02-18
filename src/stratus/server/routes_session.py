"""Session routes: init, list, context inject."""

from __future__ import annotations

from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


class SessionInitRequest(BaseModel):
    content_session_id: str
    project: str
    prompt: str | None = None


async def session_init(request: Request) -> JSONResponse:
    try:
        body = await request.json()
        req = SessionInitRequest.model_validate(body)
    except Exception:
        return JSONResponse(
            {"error": "content_session_id and project are required"},
            status_code=422,
        )

    db = request.app.state.db
    session = db.init_session(req.content_session_id, req.project, req.prompt)
    return JSONResponse(session.model_dump())


async def list_sessions(request: Request) -> JSONResponse:
    limit = int(request.query_params.get("limit", "50"))
    offset = int(request.query_params.get("offset", "0"))

    db = request.app.state.db
    sessions = db.list_sessions(limit=limit, offset=offset)
    return JSONResponse({"sessions": [s.model_dump() for s in sessions]})


async def context_inject(request: Request) -> JSONResponse:
    project = request.query_params.get("project")
    db = request.app.state.db

    # Gather recent events for context restoration
    recent_events = db.recent_events(project=project, limit=10)
    sessions = db.list_sessions(limit=1)

    context_parts = []
    if sessions:
        s = sessions[0]
        context_parts.append(f"Active session: {s.content_session_id} ({s.project})")
        if s.initial_prompt:
            context_parts.append(f"Original task: {s.initial_prompt}")

    if recent_events:
        context_parts.append(f"\nRecent memories ({len(recent_events)}):")
        for e in recent_events:
            prefix = f"[{e.type}]"
            title = e.title or e.text[:60]
            context_parts.append(f"  {prefix} {title}")

    return JSONResponse(
        {
            "context": "\n".join(context_parts) if context_parts else "No context available.",
            "event_count": len(recent_events),
            "session_count": len(sessions),
        }
    )


routes = [
    Route("/api/sessions/init", session_init, methods=["POST"]),
    Route("/api/sessions", list_sessions),
    Route("/api/context/inject", context_inject),
]
