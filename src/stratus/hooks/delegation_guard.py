"""PreToolUse delegation guard hook.

Enforces delegation boundaries during orchestrated workflows.
Blocks writes during VERIFY phase. Warns during IMPLEMENT phase.
Doc/config files always allowed. NEVER crashes — errors swallowed with exit 0.
"""

from __future__ import annotations

import sys

# File extensions that are always allowed (docs, config)
_ALLOWED_EXTENSIONS = frozenset({
    ".md", ".json", ".yaml", ".yml", ".toml", ".cfg", ".txt",
    ".gitignore", ".env", ".env.example",
})


def _get_active_phase() -> str | None:
    """Read the current orchestration phase. Returns None if no orchestration active."""
    try:
        from stratus.hooks._common import get_session_dir
        from stratus.session.state import resolve_session_id

        session_id = resolve_session_id()
        session_dir = get_session_dir(session_id)

        # Check spec state first (default mode)
        try:
            from stratus.orchestration.spec_state import read_spec_state
            state = read_spec_state(session_dir)
            if state is not None:
                return state.phase
        except ImportError:
            pass

        # Check delivery state (swords mode)
        try:
            from stratus.orchestration.delivery_state import read_delivery_state
            state = read_delivery_state(session_dir)
            if state is not None:
                return state.delivery_phase.value
        except (ImportError, AttributeError):
            pass

        return None
    except Exception:
        return None


def _is_allowed_file(file_path: str) -> bool:
    """Check if file is doc/config (always allowed)."""
    if not file_path:
        return False
    lower = file_path.lower()
    # Check extension
    for ext in _ALLOWED_EXTENSIONS:
        if lower.endswith(ext):
            return True
    # Check filename patterns
    basename = lower.rsplit("/", 1)[-1] if "/" in lower else lower
    if basename.startswith("."):
        return True  # dotfiles are config
    return False


def evaluate_guard(
    tool_name: str,
    file_path: str | None,
    phase: str | None,
) -> tuple[int, str]:
    """Evaluate delegation guard. Returns (exit_code, message).

    Pure function for testability — does not read state.
    """
    if tool_name not in ("Write", "Edit", "NotebookEdit"):
        return 0, ""

    # Doc/config files always allowed
    if file_path and _is_allowed_file(file_path):
        return 0, ""

    # No orchestration → no enforcement
    if phase is None:
        return 0, ""

    # VERIFY phase → hard block
    if phase == "verify":
        return 2, (
            f"Write operations are blocked during VERIFY phase. "
            f"Tool '{tool_name}' on '{file_path or 'unknown'}' rejected. "
            f"Verification should only read and analyze code."
        )

    # IMPLEMENT phase → warning only (can't distinguish coordinator from agent)
    if phase in ("implement", "implementation"):
        return 0, (
            f"Delegation reminder: '{tool_name}' on '{file_path or 'unknown'}'. "
            f"Implementation should be delegated to specialized agents via Task tool."
        )

    # Other phases → informational
    return 0, ""


def main() -> None:
    """Entry point for PreToolUse delegation guard hook."""
    try:
        from stratus.hooks._common import read_hook_input

        payload = read_hook_input()
        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input", {})

        # Extract file path from tool input
        file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""

        phase = _get_active_phase()
        exit_code, msg = evaluate_guard(tool_name, file_path, phase)

        if msg:
            print(msg, file=sys.stderr)
        sys.exit(exit_code)
    except Exception:
        sys.exit(0)  # Never crash


if __name__ == "__main__":
    main()
