"""Learning routes: analyze, proposals, decide, config, stats."""

from __future__ import annotations

from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from stratus.learning.models import Decision


class DecideRequest(BaseModel):
    proposal_id: str
    decision: Decision
    edited_content: str | None = None


async def analyze(request: Request) -> JSONResponse:
    """POST /api/learning/analyze — trigger analysis."""
    watcher = request.app.state.learning_watcher
    if watcher is None:
        return JSONResponse({"error": "Learning not initialized"}, status_code=503)

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    result = watcher.analyze_changes(
        since_commit=body.get("since_commit"),
        scope=body.get("scope"),
    )
    return JSONResponse({
        "detections": len(result.detections),
        "analyzed_commits": result.analyzed_commits,
        "analysis_time_ms": result.analysis_time_ms,
    })


async def get_proposals(request: Request) -> JSONResponse:
    """GET /api/learning/proposals"""
    db = request.app.state.learning_db
    try:
        max_count = int(request.query_params.get("max_count", "50"))
        min_confidence = float(request.query_params.get("min_confidence", "0.0"))
    except ValueError:
        return JSONResponse(
            {"error": "max_count must be an integer and min_confidence must be a float"},
            status_code=400,
        )
    max_count = min(max(max_count, 1), 200)

    proposals = db.list_proposals(min_confidence=min_confidence, limit=max_count)
    return JSONResponse({
        "proposals": [p.model_dump() for p in proposals],
        "count": len(proposals),
    })


async def decide(request: Request) -> JSONResponse:
    """POST /api/learning/decide"""
    try:
        body = await request.json()
        req = DecideRequest.model_validate(body)
    except Exception:
        return JSONResponse({"error": "proposal_id and decision required"}, status_code=422)

    watcher = request.app.state.learning_watcher
    if watcher is None:
        return JSONResponse({"error": "Learning not initialized"}, status_code=503)

    result = watcher.decide_proposal(req.proposal_id, req.decision, req.edited_content)
    return JSONResponse(result)


async def get_config(request: Request) -> JSONResponse:
    """GET /api/learning/config"""
    config = request.app.state.learning_config
    return JSONResponse({
        "global_enabled": config.global_enabled,
        "sensitivity": config.sensitivity.value,
        "max_proposals_per_session": config.max_proposals_per_session,
        "cooldown_days": config.cooldown_days,
        "min_confidence": config.min_confidence,
        "batch_frequency": config.batch_frequency,
        "commit_batch_threshold": config.commit_batch_threshold,
        "min_age_hours": config.min_age_hours,
    })


async def put_config(request: Request) -> JSONResponse:
    """PUT /api/learning/config"""
    body = await request.json()
    config = request.app.state.learning_config
    if "global_enabled" in body:
        config.global_enabled = body["global_enabled"]
    if "sensitivity" in body:
        from stratus.learning.models import Sensitivity
        config.sensitivity = Sensitivity(body["sensitivity"])
    if "max_proposals_per_session" in body:
        config.max_proposals_per_session = body["max_proposals_per_session"]
    if "cooldown_days" in body:
        config.cooldown_days = body["cooldown_days"]
    return JSONResponse({
        "global_enabled": config.global_enabled,
        "sensitivity": config.sensitivity.value,
    })


async def stats(request: Request) -> JSONResponse:
    """GET /api/learning/stats"""
    db = request.app.state.learning_db
    return JSONResponse(db.stats())


routes = [
    Route("/api/learning/analyze", analyze, methods=["POST"]),
    Route("/api/learning/proposals", get_proposals),
    Route("/api/learning/decide", decide, methods=["POST"]),
    Route("/api/learning/config", get_config),
    Route("/api/learning/config", put_config, methods=["PUT"]),
    Route("/api/learning/stats", stats),
]
