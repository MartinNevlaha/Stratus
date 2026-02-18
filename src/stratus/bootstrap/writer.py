"""Bootstrap config writers: project-graph.json and .ai-framework.json."""

from __future__ import annotations

import json
from pathlib import Path

from stratus.bootstrap.models import ProjectGraph, ServiceType


def write_project_graph(graph: ProjectGraph, root: Path) -> Path:
    """Write project-graph.json to repo root. Returns path."""
    path = root / "project-graph.json"
    path.write_text(graph.model_dump_json(indent=2))
    return path


def write_ai_framework_config(
    root: Path, graph: ProjectGraph, *, force: bool = False
) -> Path | None:
    """Write .ai-framework.json if not exists (or force=True). Returns None if skipped."""
    path = root / ".ai-framework.json"
    if path.exists() and not force:
        return None
    config = _build_default_config(root, graph)
    path.write_text(json.dumps(config, indent=2))
    return path


def _build_default_config(root: Path, graph: ProjectGraph) -> dict[str, object]:
    """Build full .ai-framework.json with detected values."""
    lang_counts: dict[str, int] = {}
    for svc in graph.services:
        lang_counts[svc.language] = lang_counts.get(svc.language, 0) + 1
    primary_lang = max(lang_counts, key=lambda k: lang_counts[k]) if lang_counts else "unknown"

    pms = {svc.package_manager for svc in graph.services if svc.package_manager}

    return {
        "version": 1,
        "project": {
            "name": root.name,
            "root": str(root),
            "primary_language": primary_lang,
            "package_managers": sorted(pms),
        },
        "retrieval": {
            "vexor": {
                "enabled": True,
                "project_root": str(root),
            },
            "devrag": {
                "enabled": False,
            },
        },
        "learning": {
            "global_enabled": False,
            "sensitivity": "conservative",
            "cooldown_days": 7,
            "max_proposals_per_session": 3,
        },
        "agent_teams": {
            "enabled": False,
        },
        "services": [
            {"name": svc.name, "type": svc.type, "path": svc.path}
            for svc in graph.services
            if svc.type != ServiceType.UNKNOWN
        ],
    }
