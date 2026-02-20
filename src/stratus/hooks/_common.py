"""Shared utilities for hook scripts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from stratus.session.config import DEFAULT_PORT, get_data_dir


def read_hook_input() -> dict[str, Any]:
    """Read JSON input from stdin. Returns empty dict on failure."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)  # type: ignore[no-any-return]
    except (json.JSONDecodeError, OSError):
        return {}


def get_session_dir(session_id: str) -> Path:
    return get_data_dir() / "sessions" / session_id


def get_api_url() -> str:
    """Read API URL from port.lock file, falling back to default."""
    lock_path = get_data_dir() / "port.lock"
    try:
        data: dict[str, Any] = json.loads(lock_path.read_text())
        port: int = data.get("port", DEFAULT_PORT)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        port = DEFAULT_PORT
    return f"http://127.0.0.1:{port}"


def get_git_root() -> Path | None:
    """Find git repo root via `git rev-parse`. Returns None if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


_SESSION_STATE_FILE = "session-state.json"


def get_project_root() -> Path | None:
    """Get the project root for the current session.

    Resolution order:
    1. AI_FRAMEWORK_PROJECT_ROOT env var (explicit override)
    2. Git root from `git rev-parse --show-toplevel`
    3. Session state file (project_root field)
    4. Current working directory

    Returns None only if all methods fail.
    """
    env_root = os.environ.get("AI_FRAMEWORK_PROJECT_ROOT")
    if env_root:
        p = Path(env_root)
        if p.is_dir():
            return p

    git_root = get_git_root()
    if git_root:
        return git_root

    session_id = os.environ.get("CLAUDE_CODE_TASK_LIST_ID", "default")
    session_dir = get_session_dir(session_id)
    state_file = session_dir / _SESSION_STATE_FILE
    if state_file.exists():
        try:
            data = json.loads(state_file.read_text())
            if "project_root" in data:
                p = Path(data["project_root"])
                if p.is_dir():
                    return p
        except (json.JSONDecodeError, OSError):
            pass

    cwd = Path.cwd()
    if cwd.exists():
        return cwd

    return None


def set_project_root(project_root: Path) -> None:
    """Persist project root to session state file."""
    session_id = os.environ.get("CLAUDE_CODE_TASK_LIST_ID", "default")
    session_dir = get_session_dir(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    state_file = session_dir / _SESSION_STATE_FILE

    existing: dict[str, Any] = {}
    if state_file.exists():
        try:
            existing = json.loads(state_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    existing["project_root"] = str(project_root.resolve())
    state_file.write_text(json.dumps(existing, indent=2))
