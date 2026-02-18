"""Read/write index-state.json and detect staleness via git."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from stratus.retrieval.models import IndexStatus

INDEX_STATE_FILENAME = "index-state.json"


def read_index_state(data_dir: Path) -> IndexStatus:
    """Read index-state.json, return IndexStatus. Return default if missing or corrupt."""
    state_file = data_dir / INDEX_STATE_FILENAME
    try:
        text = state_file.read_text()
        data = json.loads(text)
        return IndexStatus(**data)
    except FileNotFoundError:
        return IndexStatus()
    except (json.JSONDecodeError, TypeError, ValueError):
        return IndexStatus()


def write_index_state(data_dir: Path, status: IndexStatus) -> None:
    """Write IndexStatus to index-state.json."""
    state_file = data_dir / INDEX_STATE_FILENAME
    data_dir.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(status.model_dump()))


def get_current_commit(project_root: Path) -> str | None:
    """Run git rev-parse HEAD, return commit hash or None on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=project_root,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None


def check_staleness(data_dir: Path, project_root: Path) -> bool:
    """Compare HEAD vs last indexed commit. Returns True if stale."""
    status = read_index_state(data_dir)
    if status.last_indexed_commit is None:
        return True
    current = get_current_commit(project_root)
    if current is None:
        return True
    return current != status.last_indexed_commit


def get_changed_files(project_root: Path, since_commit: str) -> list[str]:
    """Run git diff --name-only <since>..HEAD, return list of changed paths."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{since_commit}..HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=project_root,
        )
        if result.returncode != 0:
            return []
        return [line for line in result.stdout.splitlines() if line]
    except Exception:
        return []
