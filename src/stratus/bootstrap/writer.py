"""Bootstrap config writers: project-graph.json and .ai-framework.json."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from stratus.bootstrap.models import ProjectGraph, ServiceType


def _atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically using tempfile + os.replace."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.write(fd, content.encode())
        os.close(fd)
        os.replace(tmp, path)
    except BaseException:
        os.close(fd)
        os.unlink(tmp)
        raise


def write_project_graph(graph: ProjectGraph, root: Path) -> Path:
    """Write project-graph.json to repo root atomically. Returns path."""
    path = root / "project-graph.json"
    _atomic_write(path, graph.model_dump_json(indent=2))
    return path


def write_ai_framework_config(
    root: Path,
    graph: ProjectGraph,
    *,
    force: bool = False,
    retrieval_config: dict | None = None,
) -> Path | None:
    """Write .ai-framework.json atomically if not exists (or force=True).

    Returns None if skipped.
    """
    path = root / ".ai-framework.json"
    if path.exists() and not force:
        return None
    config = _build_default_config(root, graph, retrieval_config=retrieval_config)
    _atomic_write(path, json.dumps(config, indent=2))
    return path


def update_ai_framework_config(root: Path, updates: dict) -> Path | None:
    """Merge updates into existing .ai-framework.json atomically.

    Returns None if file doesn't exist.
    """
    import sys

    path = root / ".ai-framework.json"
    if not path.exists():
        return None
    try:
        existing = json.loads(path.read_text())
    except json.JSONDecodeError:
        print(f"Warning: {path} contains invalid JSON, falling back to empty dict", file=sys.stderr)
        existing = {}
    existing.update(updates)
    _atomic_write(path, json.dumps(existing, indent=2))
    return path


def _build_default_config(
    root: Path,
    graph: ProjectGraph,
    *,
    retrieval_config: dict | None = None,
) -> dict[str, object]:
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
        "retrieval": retrieval_config
        if retrieval_config is not None
        else {
            "vexor": {
                "enabled": True,
                "project_root": str(root),
            },
            "devrag": {
                "enabled": False,
            },
        },
        "learning": {
            "global_enabled": True,
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
