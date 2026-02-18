"""SessionEnd hook: cleanup and save session summary."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]


def save_session_summary(session_dir: Path, session_id: str) -> None:
    """POST session summary to memory API. Best-effort, 2s timeout."""
    try:
        from stratus.hooks._common import get_api_url

        api_url = get_api_url()
        httpx.post(
            f"{api_url}/api/memory/save",
            json={
                "text": f"Session {session_id} ended",
                "title": "Session end",
                "type": "decision",
                "actor": "hook",
                "tags": ["session-end"],
                "session_id": session_id,
            },
            timeout=2.0,
        )
    except Exception:
        pass  # Best-effort


def cleanup_worktree_stashes(git_root: Path | None) -> None:
    """Remove ai-framework stashes. Best-effort."""
    if git_root is None:
        return
    try:
        result = subprocess.run(
            ["git", "stash", "list"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=git_root,
        )
        if result.returncode != 0:
            return
        for i, line in enumerate(reversed(result.stdout.splitlines())):
            if "ai-framework:" in line:
                subprocess.run(
                    ["git", "stash", "drop", f"stash@{{{i}}}"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    cwd=git_root,
                )
    except Exception:
        pass  # Best-effort


def write_exit_log(session_dir: Path, session_id: str) -> None:
    """Write exit log JSON with timestamp."""
    try:
        session_dir.mkdir(parents=True, exist_ok=True)
        log = {
            "session_id": session_id,
            "exited_at": datetime.now(UTC).isoformat(),
            "summary": "Session ended normally",
        }
        (session_dir / "exit-log.json").write_text(json.dumps(log, indent=2))
    except OSError:
        pass  # Best-effort


def get_git_root() -> Path | None:
    """Thin wrapper to import get_git_root at call time (avoids circular issues)."""
    from stratus.hooks._common import get_git_root as _get_git_root

    return _get_git_root()


def main() -> None:
    """Entry point for SessionEnd hook."""
    from stratus.hooks._common import get_session_dir
    from stratus.session.state import resolve_session_id

    session_id = resolve_session_id()
    session_dir = get_session_dir(session_id)

    save_session_summary(session_dir, session_id)
    cleanup_worktree_stashes(get_git_root())
    write_exit_log(session_dir, session_id)
    sys.exit(0)


if __name__ == "__main__":
    main()
