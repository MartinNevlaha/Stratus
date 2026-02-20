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

    return JSONResponse(
        {
            "active": state.phase != "learn",
            "phase": state.phase,
            "slug": state.slug,
            "current_task": state.current_task,
            "total_tasks": state.total_tasks,
            "completed_tasks": state.completed_tasks,
            "review_iteration": state.review_iteration,
            "plan_status": state.plan_status,
            "backend": coordinator._mode,
        }
    )


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

    return JSONResponse(
        {
            "slug": state.slug,
            "phase": state.phase,
            "plan_status": state.plan_status,
        }
    )


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

    return JSONResponse(
        {
            "phase": state.phase,
            "total_tasks": state.total_tasks,
            "plan_status": state.plan_status,
        }
    )


async def start_task(request: Request) -> JSONResponse:
    """POST /api/orchestration/start-task — mark a task as started."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=422)

    task_num = body.get("task_num")
    if task_num is None:
        return JSONResponse({"error": "task_num is required"}, status_code=422)

    coordinator = request.app.state.coordinator
    try:
        state = coordinator.start_task(task_num)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=409)

    return JSONResponse(
        {
            "phase": state.phase,
            "current_task": state.current_task,
        }
    )


async def complete_task(request: Request) -> JSONResponse:
    """POST /api/orchestration/complete-task — mark a task as completed."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=422)

    task_num = body.get("task_num")
    if task_num is None:
        return JSONResponse({"error": "task_num is required"}, status_code=422)

    coordinator = request.app.state.coordinator
    try:
        state = coordinator.complete_task(task_num)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=409)

    return JSONResponse(
        {
            "phase": state.phase,
            "current_task": state.current_task,
            "completed_tasks": state.completed_tasks,
            "all_done": coordinator.all_tasks_done(),
        }
    )


async def start_verify(request: Request) -> JSONResponse:
    """POST /api/orchestration/start-verify — transition to verify phase."""
    coordinator = request.app.state.coordinator
    try:
        state = coordinator.start_verify()
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=409)

    return JSONResponse(
        {
            "phase": state.phase,
            "plan_status": state.plan_status,
        }
    )


async def record_verdicts(request: Request) -> JSONResponse:
    """POST /api/orchestration/record-verdicts — record reviewer verdicts."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=422)

    raw_verdicts = body.get("verdicts")
    if not isinstance(raw_verdicts, list):
        return JSONResponse({"error": "verdicts must be a list"}, status_code=422)

    from stratus.orchestration.models import ReviewVerdict

    coordinator = request.app.state.coordinator
    try:
        verdicts = [ReviewVerdict.model_validate(v) for v in raw_verdicts]
        result = coordinator.record_verdicts(verdicts)
    except (ValueError, Exception) as e:
        return JSONResponse({"error": str(e)}, status_code=409)

    try:
        needs_fix = coordinator.needs_fix_loop()
    except ValueError:
        needs_fix = False

    return JSONResponse(
        {
            **result,
            "needs_fix": needs_fix,
        }
    )


async def start_fix_loop(request: Request) -> JSONResponse:
    """POST /api/orchestration/start-fix-loop — return to implement after failed review."""
    coordinator = request.app.state.coordinator
    try:
        state = coordinator.start_fix_loop()
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=409)

    return JSONResponse(
        {
            "phase": state.phase,
            "review_iteration": state.review_iteration,
        }
    )


async def start_learn(request: Request) -> JSONResponse:
    """POST /api/orchestration/start-learn — transition to learn phase."""
    coordinator = request.app.state.coordinator
    try:
        state = coordinator.start_learn()
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=409)

    return JSONResponse(
        {
            "phase": state.phase,
        }
    )


async def complete_spec(request: Request) -> JSONResponse:
    """POST /api/orchestration/complete — mark spec as complete."""
    coordinator = request.app.state.coordinator
    try:
        state = coordinator.complete_spec()
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=409)

    return JSONResponse(
        {
            "phase": state.phase,
            "plan_status": state.plan_status,
        }
    )


async def get_verdicts(request: Request) -> JSONResponse:
    """GET /api/orchestration/verdicts — latest review verdicts."""
    coordinator = request.app.state.coordinator
    verdicts = coordinator._last_verdicts
    return JSONResponse(
        {
            "verdicts": [v.model_dump() for v in verdicts],
            "count": len(verdicts),
        }
    )


async def get_team(request: Request) -> JSONResponse:
    """GET /api/orchestration/team — team info."""
    team_config = request.app.state.team_config
    return JSONResponse(
        {
            "enabled": team_config.mode == "agent-teams",
            "mode": team_config.mode,
            "teammate_mode": team_config.teammate_mode,
            "delegate_mode": team_config.delegate_mode,
            "max_teammates": team_config.max_teammates,
        }
    )


routes = [
    Route("/api/orchestration/state", get_state),
    Route("/api/orchestration/start", start_spec, methods=["POST"]),
    Route("/api/orchestration/approve-plan", approve_plan, methods=["POST"]),
    Route("/api/orchestration/start-task", start_task, methods=["POST"]),
    Route("/api/orchestration/complete-task", complete_task, methods=["POST"]),
    Route("/api/orchestration/start-verify", start_verify, methods=["POST"]),
    Route("/api/orchestration/record-verdicts", record_verdicts, methods=["POST"]),
    Route("/api/orchestration/start-fix-loop", start_fix_loop, methods=["POST"]),
    Route("/api/orchestration/start-learn", start_learn, methods=["POST"]),
    Route("/api/orchestration/complete", complete_spec, methods=["POST"]),
    Route("/api/orchestration/verdicts", get_verdicts),
    Route("/api/orchestration/team", get_team),
]
