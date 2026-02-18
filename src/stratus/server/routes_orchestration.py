"""Orchestration routes: spec state, team info, lifecycle control."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


async def get_state(request: Request) -> JSONResponse:
    """GET /api/orchestration/state — current SpecState + backend info."""
    coordinator = request.app.state.coordinator
    state = coordinator.get_state()
    if state is None:
        return JSONResponse({"active": False})

    return JSONResponse({
        "active": state.phase != "learn",
        "phase": state.phase,
        "slug": state.slug,
        "current_task": state.current_task,
        "total_tasks": state.total_tasks,
        "completed_tasks": state.completed_tasks,
        "review_iteration": state.review_iteration,
        "plan_status": state.plan_status,
        "backend": coordinator._mode,
    })


async def start_spec(request: Request) -> JSONResponse:
    """POST /api/orchestration/start — start a new spec cycle."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=422)

    slug = body.get("slug")
    if not slug:
        return JSONResponse({"error": "slug is required"}, status_code=422)

    coordinator = request.app.state.coordinator
    try:
        state = coordinator.start_spec(
            slug=slug,
            plan_path=body.get("plan_path"),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=409)

    return JSONResponse({
        "slug": state.slug,
        "phase": state.phase,
        "plan_status": state.plan_status,
    })


async def approve_plan(request: Request) -> JSONResponse:
    """POST /api/orchestration/approve-plan — approve the plan phase."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=422)

    coordinator = request.app.state.coordinator
    try:
        state = coordinator.approve_plan(
            total_tasks=body.get("total_tasks", 0),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=409)

    return JSONResponse({
        "phase": state.phase,
        "total_tasks": state.total_tasks,
        "plan_status": state.plan_status,
    })


async def get_verdicts(request: Request) -> JSONResponse:
    """GET /api/orchestration/verdicts — latest review verdicts."""
    coordinator = request.app.state.coordinator
    verdicts = coordinator._last_verdicts
    return JSONResponse({
        "verdicts": [v.model_dump() for v in verdicts],
        "count": len(verdicts),
    })


async def get_team(request: Request) -> JSONResponse:
    """GET /api/orchestration/team — team info."""
    team_config = request.app.state.team_config
    return JSONResponse({
        "enabled": team_config.mode == "agent-teams",
        "mode": team_config.mode,
        "teammate_mode": team_config.teammate_mode,
        "delegate_mode": team_config.delegate_mode,
        "max_teammates": team_config.max_teammates,
    })


routes = [
    Route("/api/orchestration/state", get_state),
    Route("/api/orchestration/start", start_spec, methods=["POST"]),
    Route("/api/orchestration/approve-plan", approve_plan, methods=["POST"]),
    Route("/api/orchestration/verdicts", get_verdicts),
    Route("/api/orchestration/team", get_team),
]
