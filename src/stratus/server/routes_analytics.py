"""Analytics routes: failure events, trends, hotspots, rule effectiveness."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from stratus.learning.analytics import (
    compute_all_rule_effectiveness,
    compute_failure_summary,
    compute_failure_trends,
    compute_file_hotspots,
    identify_systematic_problems,
)
from stratus.learning.models import FailureCategory, FailureEvent


async def record_failure(request: Request) -> JSONResponse:
    """POST /api/learning/analytics/record-failure — record a failure event."""
    body = await request.json()
    category = body.get("category")
    if not category:
        return JSONResponse({"error": "category required"}, status_code=422)

    try:
        failure_category = FailureCategory(category)
    except ValueError:
        return JSONResponse({"error": f"unknown category: {category!r}"}, status_code=422)

    event = FailureEvent(
        category=failure_category,
        file_path=body.get("file_path"),
        detail=body.get("detail", ""),
        session_id=body.get("session_id"),
    )
    db = request.app.state.learning_db
    event_id = db.analytics.record_failure(event)
    return JSONResponse({"id": event_id, "signature": event.signature})


async def failures_summary(request: Request) -> JSONResponse:
    """GET /api/learning/analytics/failures/summary"""
    try:
        days = int(request.query_params.get("days", "30"))
    except ValueError:
        return JSONResponse({"error": "days must be an integer"}, status_code=400)
    days = min(max(days, 1), 365)
    db = request.app.state.learning_db
    summary = compute_failure_summary(db.analytics, days=days)
    # FailureCategory enum keys → string values for JSON serialisation
    summary["by_category"] = {
        k.value if hasattr(k, "value") else k: v
        for k, v in summary["by_category"].items()
    }
    return JSONResponse(summary)


async def failures_trends(request: Request) -> JSONResponse:
    """GET /api/learning/analytics/failures/trends"""
    try:
        days = int(request.query_params.get("days", "30"))
    except ValueError:
        return JSONResponse({"error": "days must be an integer"}, status_code=400)
    days = min(max(days, 1), 365)

    category_param = request.query_params.get("category")
    if category_param:
        try:
            category: FailureCategory | None = FailureCategory(category_param)
        except ValueError:
            return JSONResponse({"error": f"unknown category: {category_param!r}"}, status_code=400)
    else:
        category = None

    db = request.app.state.learning_db
    trends = compute_failure_trends(db.analytics, days=days, category=category)
    return JSONResponse({"trends": [t.model_dump() for t in trends]})


async def failures_hotspots(request: Request) -> JSONResponse:
    """GET /api/learning/analytics/failures/hotspots"""
    try:
        limit = int(request.query_params.get("limit", "10"))
        days = int(request.query_params.get("days", "30"))
    except ValueError:
        return JSONResponse({"error": "limit and days must be integers"}, status_code=400)
    limit = min(max(limit, 0), 1000)
    days = min(max(days, 1), 365)

    db = request.app.state.learning_db
    hotspots = compute_file_hotspots(db.analytics, limit=limit, days=days)
    return JSONResponse({"hotspots": [h.model_dump() for h in hotspots]})


async def failures_systematic(request: Request) -> JSONResponse:
    """GET /api/learning/analytics/failures/systematic"""
    try:
        days = int(request.query_params.get("days", "30"))
        min_count = int(request.query_params.get("min_count", "5"))
    except ValueError:
        return JSONResponse({"error": "days and min_count must be integers"}, status_code=400)
    days = min(max(days, 1), 365)
    min_count = min(max(min_count, 1), 1000)

    db = request.app.state.learning_db
    problems = identify_systematic_problems(db.analytics, days=days, min_count=min_count)
    # Serialise FailureCategory enum values in each problem dict
    serialised = [
        {**p, "category": p["category"].value if hasattr(p["category"], "value") else p["category"]}
        for p in problems
    ]
    return JSONResponse({"problems": serialised})


async def rules_effectiveness(request: Request) -> JSONResponse:
    """GET /api/learning/analytics/rules/effectiveness"""
    db = request.app.state.learning_db
    results = compute_all_rule_effectiveness(db.analytics)
    return JSONResponse({"rules": [r.model_dump() for r in results]})


async def rules_low_impact(request: Request) -> JSONResponse:
    """GET /api/learning/analytics/rules/low-impact"""
    db = request.app.state.learning_db
    all_results = compute_all_rule_effectiveness(db.analytics)
    low_impact = [r for r in all_results if r.verdict != "effective"]
    return JSONResponse({
        "rules": [r.model_dump() for r in low_impact],
        "count": len(low_impact),
    })


routes = [
    Route(
        "/api/learning/analytics/record-failure",
        record_failure,
        methods=["POST"],
    ),
    Route("/api/learning/analytics/failures/summary", failures_summary),
    Route("/api/learning/analytics/failures/trends", failures_trends),
    Route("/api/learning/analytics/failures/hotspots", failures_hotspots),
    Route("/api/learning/analytics/failures/systematic", failures_systematic),
    Route("/api/learning/analytics/rules/effectiveness", rules_effectiveness),
    Route("/api/learning/analytics/rules/low-impact", rules_low_impact),
]
