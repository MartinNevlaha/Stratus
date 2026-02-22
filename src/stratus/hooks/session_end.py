"""SessionEnd hook: cleanup and persist session state."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path


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
        lines = result.stdout.splitlines()
        indices = [i for i, line in enumerate(lines) if "ai-framework:" in line]
        for idx in reversed(indices):
            subprocess.run(
                ["git", "stash", "drop", f"stash@{{{idx}}}"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=git_root,
            )
    except Exception:
        pass


def write_exit_log(session_dir: Path, session_id: str) -> None:
    """Write exit log JSON with timestamp."""
    try:
        session_dir.mkdir(parents=True, exist_ok=True)
        log = {
            "session_id": session_id,
            "exited_at": datetime.now(UTC).isoformat(),
            "summary": "Session ended normally",
        }
        path = session_dir / "exit-log.json"
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            os.write(fd, json.dumps(log, indent=2).encode())
            os.close(fd)
            os.replace(tmp, path)
        except BaseException:
            os.close(fd)
            os.unlink(tmp)
            raise
    except OSError:
        pass


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

    cleanup_worktree_stashes(get_git_root())
    write_exit_log(session_dir, session_id)
    sys.exit(0)


if __name__ == "__main__":
    main()
