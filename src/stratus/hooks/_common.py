"""Shared utilities for hook scripts."""

from __future__ import annotations

import json
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
