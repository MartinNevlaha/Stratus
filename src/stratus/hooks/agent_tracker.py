"""PreToolUse/PostToolUse hook: track active agent in dashboard.

On PreToolUse[Task]: extracts subagent_type and sets active_agent_id.
On PostToolUse[Task]: clears active_agent_id.

Works in all phases. Never crashes - errors are swallowed with exit 0.
"""

from __future__ import annotations

import sys
from typing import Any


def _get_active_phase() -> str | None:
    """Read the current orchestration phase. Returns None if no orchestration active."""
    try:
        from stratus.hooks._common import get_session_dir
        from stratus.session.state import resolve_session_id

        session_id = resolve_session_id()
        session_dir = get_session_dir(session_id)

        try:
            from stratus.orchestration.spec_state import read_spec_state

            state = read_spec_state(session_dir)
            if state is not None:
                return state.phase
        except ImportError:
            pass

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


def _call_api(agent_id: str | None) -> bool:
    """Call the set-active-agent API. Returns True on success."""
    try:
        import httpx

        from stratus.hooks._common import get_api_url

        api_url = get_api_url()
        with httpx.Client(timeout=0.5) as client:
            resp = client.post(
                f"{api_url}/api/orchestration/set-active-agent",
                json={"agent_id": agent_id},
            )
            return resp.status_code == 200
    except Exception:
        return False


def handle_pre_tool_use(tool_input: dict[str, Any], phase: str | None) -> None:
    """Handle PreToolUse event - set active agent if in any orchestration."""
    if phase is None:
        return

    subagent_type = tool_input.get("subagent_type")
    if not subagent_type:
        return

    _call_api(subagent_type)


def handle_post_tool_use(phase: str | None) -> None:
    """Handle PostToolUse event - clear active agent if in any orchestration."""
    if phase is None:
        return

    _call_api(None)


def main() -> None:
    """Entry point for PreToolUse/PostToolUse agent tracker hook."""
    try:
        from stratus.hooks._common import read_hook_input

        payload = read_hook_input()
        event_name = payload.get("hook_event_name", "")
        tool_name = payload.get("tool_name", "")

        if tool_name != "Task":
            sys.exit(0)

        phase = _get_active_phase()

        if event_name == "PreToolUse":
            tool_input = payload.get("tool_input", {})
            handle_pre_tool_use(tool_input, phase)
        elif event_name == "PostToolUse":
            handle_post_tool_use(phase)
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
