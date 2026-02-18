"""Delivery routes: state, start, advance, skip, fix-loop, complete, roles."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

_NOT_ENABLED = JSONResponse({"error": "Delivery framework not enabled"}, status_code=503)


def _get_coordinator(request: Request):  # noqa: ANN202
    """Return delivery coordinator or None."""
    return getattr(request.app.state, "delivery_coordinator", None)


async def get_state(request: Request) -> JSONResponse:
    """GET /api/delivery/state — return current delivery state."""
    coordinator = _get_coordinator(request)
    if coordinator is None:
        return _NOT_ENABLED
    state = coordinator.get_state()
    if state is None:
        return JSONResponse({"active": False})
    data = state.model_dump()
    data["active"] = True
    return JSONResponse(data)


async def start_delivery(request: Request) -> JSONResponse:
    """POST /api/delivery/start — start delivery (body: slug, mode, plan_path)."""
    coordinator = _get_coordinator(request)
    if coordinator is None:
        return _NOT_ENABLED

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=422)

    slug = body.get("slug")
    if not slug:
        return JSONResponse({"error": "slug is required"}, status_code=422)

    if coordinator.get_state() is not None:
        return JSONResponse({"error": "Delivery already active"}, status_code=409)

    mode = body.get("mode", "classic")
    try:
        coordinator.set_mode(mode)
    except ValueError:
        return JSONResponse({"error": f"Invalid mode: {mode}"}, status_code=422)

    try:
        state = coordinator.start_delivery(
            slug=slug,
            plan_path=body.get("plan_path"),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=409)

    return JSONResponse(state.model_dump())


async def advance_phase(request: Request) -> JSONResponse:
    """POST /api/delivery/advance — advance to next phase."""
    coordinator = _get_coordinator(request)
    if coordinator is None:
        return _NOT_ENABLED
    try:
        state = coordinator.advance_phase()
    except (ValueError, RuntimeError) as e:
        return JSONResponse({"error": str(e)}, status_code=409)
    return JSONResponse(state.model_dump())


async def skip_phase(request: Request) -> JSONResponse:
    """POST /api/delivery/skip — skip current phase (body: reason)."""
    coordinator = _get_coordinator(request)
    if coordinator is None:
        return _NOT_ENABLED

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=422)

    reason = body.get("reason")
    if not reason:
        return JSONResponse({"error": "reason is required"}, status_code=422)

    try:
        state = coordinator.skip_phase(reason)
    except (ValueError, RuntimeError) as e:
        return JSONResponse({"error": str(e)}, status_code=409)
    return JSONResponse(state.model_dump())


async def fix_loop(request: Request) -> JSONResponse:
    """POST /api/delivery/fix-loop — start fix loop back to IMPLEMENTATION."""
    coordinator = _get_coordinator(request)
    if coordinator is None:
        return _NOT_ENABLED
    try:
        state = coordinator.start_fix_loop()
    except (ValueError, RuntimeError) as e:
        return JSONResponse({"error": str(e)}, status_code=409)
    return JSONResponse(state.model_dump())


async def complete_delivery(request: Request) -> JSONResponse:
    """POST /api/delivery/complete — complete delivery from LEARNING."""
    coordinator = _get_coordinator(request)
    if coordinator is None:
        return _NOT_ENABLED
    try:
        state = coordinator.complete_delivery()
    except (ValueError, RuntimeError) as e:
        return JSONResponse({"error": str(e)}, status_code=409)
    return JSONResponse(state.model_dump())


async def get_roles(request: Request) -> JSONResponse:
    """GET /api/delivery/roles — active roles for current phase."""
    coordinator = _get_coordinator(request)
    if coordinator is None:
        return _NOT_ENABLED
    state = coordinator.get_state()
    if state is None:
        return JSONResponse({"roles": [], "phase_lead": None})
    return JSONResponse(
        {
            "roles": coordinator.get_active_roles(),
            "phase_lead": state.phase_lead,
            "delivery_phase": state.delivery_phase,
        }
    )


async def get_dispatch(request: Request) -> JSONResponse:
    """GET /api/delivery/dispatch — dispatch context for classic mode."""
    coordinator = _get_coordinator(request)
    if coordinator is None:
        return _NOT_ENABLED
    state = coordinator.get_state()
    if state is None:
        return JSONResponse({"active": False})

    from stratus.orchestration.delivery_dispatch import (
        DeliveryDispatcher,
    )

    dispatcher = DeliveryDispatcher()
    return JSONResponse(dispatcher.build_dispatch_context(state))


async def post_dispatch_assignments(request: Request) -> JSONResponse:
    """POST /api/delivery/dispatch/assignments — task assignment suggestions."""
    coordinator = _get_coordinator(request)
    if coordinator is None:
        return _NOT_ENABLED
    state = coordinator.get_state()
    if state is None:
        return JSONResponse({"active": False})

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=422)

    from stratus.orchestration.delivery_dispatch import (
        DeliveryDispatcher,
    )

    tasks = body.get("tasks", [])
    dispatcher = DeliveryDispatcher()
    assignments = dispatcher.build_task_assignments(state, tasks)
    return JSONResponse({"assignments": assignments})


routes = [
    Route("/api/delivery/state", get_state),
    Route("/api/delivery/start", start_delivery, methods=["POST"]),
    Route("/api/delivery/advance", advance_phase, methods=["POST"]),
    Route("/api/delivery/skip", skip_phase, methods=["POST"]),
    Route("/api/delivery/fix-loop", fix_loop, methods=["POST"]),
    Route("/api/delivery/complete", complete_delivery, methods=["POST"]),
    Route("/api/delivery/roles", get_roles),
    Route("/api/delivery/dispatch", get_dispatch),
    Route(
        "/api/delivery/dispatch/assignments",
        post_dispatch_assignments,
        methods=["POST"],
    ),
]
