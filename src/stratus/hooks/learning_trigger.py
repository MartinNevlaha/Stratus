"""PostToolUse hook: detect git commit/merge, trigger learning analysis."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

from stratus.hooks._common import get_git_root


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON data to path atomically using tempfile + os.replace."""
    content = json.dumps(data)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.write(fd, content.encode())
        os.close(fd)
        os.replace(tmp, path)
    except BaseException:
        os.close(fd)
        os.unlink(tmp)
        raise


_GIT_COMMIT_RE = re.compile(r"git\s+(commit|merge|pull)\b")


def is_git_commit_command(command: str) -> bool:
    """Check if a shell command is a git commit/merge/pull."""
    return bool(_GIT_COMMIT_RE.search(command))


def should_trigger_analysis(state_file: Path, threshold: int = 5) -> bool:
    """Check if commit count has reached the batch threshold.

    Returns True and resets counter if threshold reached.
    """
    try:
        data = json.loads(state_file.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False

    count = data.get("commit_count", 0)
    if count + 1 >= threshold:
        data["commit_count"] = 0
        _atomic_write_json(state_file, data)
        return True
    return False


def _increment_commit_count(state_file: Path) -> None:
    """Increment the commit counter in the state file atomically."""
    try:
        data = json.loads(state_file.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        data = {}
    data["commit_count"] = data.get("commit_count", 0) + 1
    state_file.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(state_file, data)


def main() -> None:
    """Entry point for PostToolUse hook."""
    from stratus.hooks._common import read_hook_input

    hook_input = read_hook_input()
    if not hook_input:
        sys.exit(0)

    # Early exit if not a Bash git commit — reindex only fires on commits
    tool_name = hook_input.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    tool_input = hook_input.get("tool_input", {})
    command = tool_input.get("command", "")
    if not is_git_commit_command(command):
        sys.exit(0)

    # Only trigger reindex if stratus is initialized in this project
    git_root = get_git_root()
    if git_root is None or not (git_root / ".ai-framework.json").exists():
        return

    # Fire reindex unconditionally on every commit (fire-and-forget)
    try:
        import httpx

        from stratus.hooks._common import get_api_url

        api_url = get_api_url()
        httpx.post(
            f"{api_url}/api/retrieval/index",
            json={"project_root": str(git_root)},
            timeout=2.0,
        )
    except Exception:
        pass  # Never block the tool

    # Check if learning is enabled before proceeding with learning logic
    from stratus.learning.config import load_learning_config

    config = load_learning_config(None)
    if not config.global_enabled:
        sys.exit(0)

    # Increment commit counter
    from stratus.session.config import get_data_dir

    state_file = get_data_dir() / "learning-state.json"
    _increment_commit_count(state_file)

    # Check if we should trigger analysis
    if should_trigger_analysis(state_file, threshold=config.commit_batch_threshold):
        try:
            import httpx

            from stratus.hooks._common import get_api_url

            api_url = get_api_url()
            httpx.post(f"{api_url}/api/learning/analyze", json={}, timeout=5.0)
        except Exception:
            pass  # Never block the tool

    sys.exit(0)


if __name__ == "__main__":
    main()
