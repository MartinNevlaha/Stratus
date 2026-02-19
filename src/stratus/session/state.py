"""Session state JSON read/write and session ID resolution."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def resolve_session_id() -> str:
    """Resolve session ID from env vars with fallback chain."""
    return os.environ.get("CLAUDE_CODE_TASK_LIST_ID", "default")


def write_state(path: Path, data: dict[str, object]) -> None:
    """Write state dict to JSON file atomically, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, indent=2)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.write(fd, content.encode())
        os.close(fd)
        os.replace(tmp, path)
    except BaseException:
        os.close(fd)
        os.unlink(tmp)
        raise


def read_state(path: Path) -> dict[str, object]:
    """Read state dict from JSON file. Returns empty dict on missing/corrupt file."""
    try:
        result: dict[str, object] = json.loads(path.read_text())  # pyright: ignore[reportAny]
        return result
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
