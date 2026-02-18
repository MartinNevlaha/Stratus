"""PreCompact hook: capture session state before compaction."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx


def capture_pre_compact_state(session_dir: Path, state: dict[str, object]) -> None:
    """Save pre-compaction state to a JSON file in the session directory."""
    session_dir.mkdir(parents=True, exist_ok=True)
    state_with_meta = {
        **state,
        "captured_at": datetime.now(UTC).isoformat(),
    }
    state_file = session_dir / "pre-compact-state.json"
    state_file.write_text(json.dumps(state_with_meta, indent=2))


def main() -> None:
    """Entry point for PreCompact hook."""
    from stratus.hooks._common import get_api_url, get_session_dir, read_hook_input
    from stratus.session.state import resolve_session_id

    hook_input = read_hook_input()
    session_id = hook_input.get("session_id") or resolve_session_id()
    session_dir = get_session_dir(session_id)

    # Gather current state from hook input
    state: dict[str, object] = {
        "plan_file": hook_input.get("plan_file"),
        "tasks": hook_input.get("tasks", []),
        "session_id": session_id,
    }

    # Include spec state if active
    from stratus.orchestration.spec_state import read_spec_state

    spec_state = read_spec_state(session_dir)
    if spec_state is not None:
        state["spec_state"] = spec_state.model_dump()

    # Include delivery state if active
    try:
        api_url = get_api_url()
        resp = httpx.get(f"{api_url}/api/delivery/state", timeout=5.0)
        delivery_data = resp.json()
        if delivery_data.get("active"):
            state["delivery_state"] = delivery_data
    except Exception:
        pass  # Delivery API not available

    # Try to save via API, fall back to file
    try:
        api_url = get_api_url()
        httpx.post(
            f"{api_url}/api/memory/save",
            json={
                "text": json.dumps(state),
                "title": "Pre-compaction state snapshot",
                "type": "decision",
                "actor": "hook",
                "tags": ["compaction", "state-snapshot"],
                "session_id": session_id,
            },
            timeout=5.0,
        )
    except Exception:
        pass  # API failure is not fatal; file save is the fallback

    capture_pre_compact_state(session_dir, state)
    print("Pre-compaction state captured.", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
