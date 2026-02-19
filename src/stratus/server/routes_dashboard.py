"""Dashboard routes: aggregated state endpoint + HTML page serving."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

from stratus import __version__ as VERSION

STATIC_DIR = Path(__file__).parent / "static"


# Agent definitions per spec phase
def _agent(id: str, category: str, model: str) -> dict[str, str]:
    return {"id": id, "label": id, "category": category, "model": model}


def _build_spec_phase_agents() -> dict[str, list[dict[str, str]]]:
    """Build SPEC_PHASE_AGENTS from the agent registry."""
    from stratus.registry.loader import AgentRegistry

    registry = AgentRegistry.load()
    result: dict[str, list[dict[str, str]]] = {}
    # Map phases to category labels
    phase_categories = {
        "plan": "planning",
        "implement": "implementation",
        "verify": "review",
        "learn": None,
    }
    for phase, category in phase_categories.items():
        agents = registry.filter_by_phase(phase)
        default_agents = [a for a in agents if "default" in a.orchestration_modes]
        if category is None:
            result[phase] = []
            continue
        result[phase] = [_agent(a.name, category, a.model) for a in default_agents]
    return result


SPEC_PHASE_AGENTS: dict[str, list[dict[str, str]]] = _build_spec_phase_agents()


def _build_orchestration(request: Request) -> dict:
    """Build orchestration section from app.state safely."""
    result: dict = {
        "mode": "inactive",
        "spec": None,
        "delivery": None,
        "team": {"enabled": False, "mode": "task-tool", "max_teammates": 0},
        "verdicts": {"verdicts": [], "count": 0},
    }

    try:
        team_config = request.app.state.team_config
        result["team"] = {
            "enabled": team_config.mode == "agent-teams",
            "mode": team_config.mode,
            "max_teammates": team_config.max_teammates,
        }
    except Exception:
        pass

    # Check spec coordinator
    try:
        coordinator = request.app.state.coordinator
        if coordinator is not None:
            state = coordinator.get_state()
            if state is not None:
                result["mode"] = "spec"
                result["spec"] = {
                    "phase": state.phase,
                    "slug": state.slug,
                    "current_task": state.current_task,
                    "total_tasks": state.total_tasks,
                    "completed_tasks": state.completed_tasks,
                    "review_iteration": state.review_iteration,
                    "plan_status": state.plan_status,
                }
                result["verdicts"] = {
                    "verdicts": [v.model_dump() for v in coordinator._last_verdicts],
                    "count": len(coordinator._last_verdicts),
                }
    except Exception:
        pass

    # Check delivery coordinator
    try:
        delivery = getattr(request.app.state, "delivery_coordinator", None)
        if delivery is not None:
            state = delivery.get_state()
            if state is not None:
                result["mode"] = "delivery"
                phase = state.delivery_phase
                phase_val = phase.value if hasattr(phase, "value") else phase
                result["delivery"] = {
                    "delivery_phase": phase_val,
                    "slug": state.slug,
                    "orchestration_mode": state.orchestration_mode,
                    "active_roles": state.active_roles,
                    "phase_lead": state.phase_lead,
                }
    except Exception:
        pass

    return result


def _get_agents(orchestration: dict) -> list[dict]:
    """Derive active agent list from orchestration state."""
    if orchestration["mode"] == "spec" and orchestration["spec"]:
        phase = orchestration["spec"]["phase"]
        agents = SPEC_PHASE_AGENTS.get(phase, [])
        return [{**a, "active": True, "role": "worker"} for a in agents]

    if orchestration["mode"] == "delivery" and orchestration["delivery"]:
        delivery = orchestration["delivery"]
        roles = delivery.get("active_roles") or []
        lead = delivery.get("phase_lead")
        return [
            {
                "id": role,
                "label": role,
                "category": "delivery",
                "model": "sonnet",
                "active": True,
                "role": "lead" if role == lead else "worker",
            }
            for role in roles
        ]

    return []


def _build_learning(request: Request) -> dict:
    """Build learning section from app.state safely."""
    result: dict = {
        "enabled": False,
        "sensitivity": "conservative",
        "proposals": {"count": 0, "pending": []},
        "stats": {"candidates": 0, "proposals": 0},
    }

    try:
        config = request.app.state.learning_config
        result["enabled"] = config.global_enabled
        result["sensitivity"] = config.sensitivity.value
    except Exception:
        pass

    try:
        db = request.app.state.learning_db
        proposals = db.list_proposals(min_confidence=0.0, limit=10)
        pending = [p for p in proposals if p.status == "pending"]
        result["proposals"] = {
            "count": len(proposals),
            "pending": [p.model_dump() for p in pending],
        }
        stats = db.stats()
        result["stats"] = {
            "candidates": stats.get("candidates_total", 0),
            "proposals": stats.get("proposals_total", 0),
        }
    except Exception:
        pass

    return result


def _build_memory(request: Request) -> dict:
    """Build memory section from app.state safely."""
    try:
        db = request.app.state.db
        stats = db.get_stats()
        return {
            "total_events": stats.get("total_events", 0),
            "total_sessions": stats.get("total_sessions", 0),
        }
    except Exception:
        return {"total_events": 0, "total_sessions": 0}


def _build_registry() -> dict:
    """Build agents, skills, and rules for the registry endpoint."""
    root = Path(os.getcwd())
    claude_dir = root / ".claude"

    agents: list[dict] = []
    try:
        from stratus.registry.loader import AgentRegistry

        agents = [a.model_dump() for a in AgentRegistry.load().all_agents()]
    except Exception:
        pass

    rules: list[dict] = []
    try:
        rules_dir = claude_dir / "rules"
        if rules_dir.is_dir():
            rules = [
                {"name": f.stem, "path": str(f.relative_to(root))}
                for f in sorted(rules_dir.glob("*.md"))
            ]
    except Exception:
        pass

    skills: list[dict] = []
    try:
        skills_dir = claude_dir / "skills"
        if skills_dir.is_dir():
            skills = [
                {"name": d.name, "path": str(d.relative_to(root))}
                for d in sorted(skills_dir.iterdir())
                if d.is_dir()
            ]
    except Exception:
        pass

    return {"agents": agents, "rules": rules, "skills": skills}


async def dashboard_registry(request: Request) -> JSONResponse:
    """GET /api/dashboard/registry — agents list + local skills + rules."""
    return JSONResponse(_build_registry())


async def dashboard_state(request: Request) -> JSONResponse:
    """GET /api/dashboard/state — aggregated dashboard data."""
    orchestration = _build_orchestration(request)
    return JSONResponse(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "version": VERSION,
            "orchestration": orchestration,
            "agents": _get_agents(orchestration),
            "learning": _build_learning(request),
            "memory": _build_memory(request),
        }
    )


async def dashboard_page(request: Request) -> FileResponse:
    """GET /dashboard — serve the dashboard HTML page."""
    return FileResponse(STATIC_DIR / "index.html", media_type="text/html")


routes = [
    Route("/api/dashboard/registry", dashboard_registry),
    Route("/api/dashboard/state", dashboard_state),
    Route("/dashboard", dashboard_page),
]
