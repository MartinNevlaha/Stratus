"""Skills and rules routes: list skills, filter by phase, validate, list rules/invariants."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from stratus.rule_engine.models import RulesSnapshot


async def list_skills(request: Request) -> JSONResponse:
    """GET /api/skills — list all discovered skills."""
    registry = request.app.state.skill_registry
    skills = registry.discover()
    return JSONResponse(
        {
            "skills": [s.model_dump() for s in skills],
            "count": len(skills),
        }
    )


async def get_skill(request: Request) -> JSONResponse:
    """GET /api/skills/{name} — get a specific skill by name."""
    name = request.path_params["name"]
    registry = request.app.state.skill_registry
    skill = registry.get(name)
    if skill is None:
        return JSONResponse({"error": f"Skill '{name}' not found"}, status_code=404)
    return JSONResponse(skill.model_dump())


async def filter_skills_by_phase(request: Request) -> JSONResponse:
    """GET /api/skills/phase/{phase} — filter skills by required phase."""
    phase = request.path_params["phase"]
    registry = request.app.state.skill_registry
    skills = registry.filter_by_phase(phase)
    return JSONResponse(
        {
            "skills": [s.model_dump() for s in skills],
            "count": len(skills),
            "phase": phase,
        }
    )


async def validate_skills(request: Request) -> JSONResponse:
    """POST /api/skills/validate — validate all skills against their agent files."""
    registry = request.app.state.skill_registry
    errors = registry.validate_all()
    return JSONResponse(
        {
            "valid": len(errors) == 0,
            "error_count": len(errors),
            "errors": [e.model_dump() for e in errors],
        }
    )


async def list_rules(request: Request) -> JSONResponse:
    """GET /api/rules — list all loaded rules and their hashes."""
    index = request.app.state.rules_index
    snapshot = index.load()
    return JSONResponse(
        {
            "rules": [r.model_dump() for r in snapshot.rules],
            "count": len(snapshot.rules),
            "snapshot_hash": snapshot.snapshot_hash,
        }
    )


async def list_invariants(request: Request) -> JSONResponse:
    """GET /api/rules/invariants — list active framework invariants."""
    index = request.app.state.rules_index
    disabled_param = request.query_params.get("disabled", "")
    disabled_ids = [d.strip() for d in disabled_param.split(",") if d.strip()]
    invariants = index.get_active_invariants(disabled_ids=disabled_ids or None)
    return JSONResponse(
        {
            "invariants": [inv.model_dump() for inv in invariants],
            "count": len(invariants),
        }
    )


async def check_immutability(request: Request) -> JSONResponse:
    """POST /api/rules/check-immutability — compare current rules against a previous snapshot."""
    try:
        body = await request.json()
        previous = RulesSnapshot.model_validate(body)
    except Exception:
        return JSONResponse({"error": "Valid RulesSnapshot body required"}, status_code=422)

    index = request.app.state.rules_index
    violations = index.check_immutability(previous)
    return JSONResponse(
        {
            "immutable": len(violations) == 0,
            "violation_count": len(violations),
            "violations": [v.model_dump() for v in violations],
        }
    )


routes = [
    Route("/api/skills", list_skills),
    Route("/api/skills/phase/{phase}", filter_skills_by_phase),
    Route("/api/skills/validate", validate_skills, methods=["POST"]),
    Route("/api/skills/{name}", get_skill),
    Route("/api/rules", list_rules),
    Route("/api/rules/invariants", list_invariants),
    Route("/api/rules/check-immutability", check_immutability, methods=["POST"]),
]
