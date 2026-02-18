"""PostToolUse phase guard hook.

Warns when agent spawning is inconsistent with current phase.
Always exit 0 — informational only. NEVER crashes.
"""

from __future__ import annotations

import sys

# Agents expected in each phase
_IMPLEMENT_AGENTS = frozenset({
    "framework-expert", "implementation-expert",
    "delivery-backend-engineer", "delivery-frontend-engineer",
    "delivery-mobile-engineer", "delivery-devops-engineer",
    "delivery-database-engineer",
})

_VERIFY_AGENTS = frozenset({
    "spec-reviewer-compliance", "spec-reviewer-quality",
    "qa-engineer", "delivery-qa-engineer",
    "delivery-code-reviewer",
})


def evaluate_phase_consistency(
    subagent_type: str | None,
    phase: str | None,
) -> str:
    """Check if spawned agent matches current phase. Returns warning message or empty string."""
    if not subagent_type or not phase:
        return ""

    agent = subagent_type.lower().strip()

    # Warn if implementation agent spawned during verify
    if phase == "verify" and agent in _IMPLEMENT_AGENTS:
        return (
            f"Phase inconsistency: agent '{subagent_type}' is an implementation agent "
            f"but current phase is VERIFY. Consider using review/QA agents instead."
        )

    # Warn if review agent spawned during implement
    if phase in ("implement", "implementation") and agent in _VERIFY_AGENTS:
        return (
            f"Phase inconsistency: agent '{subagent_type}' is a review agent "
            f"but current phase is IMPLEMENT. Consider using implementation agents instead."
        )

    return ""


def main() -> None:
    """Entry point for PostToolUse phase guard hook."""
    try:
        from stratus.hooks._common import read_hook_input

        payload = read_hook_input()
        tool_name = payload.get("tool_name", "")

        if tool_name != "Task":
            sys.exit(0)

        tool_input = payload.get("tool_input", {})
        subagent_type = tool_input.get("subagent_type")

        # Get current phase
        phase = None
        try:
            from stratus.hooks._common import get_session_dir
            from stratus.session.state import resolve_session_id

            session_id = resolve_session_id()
            session_dir = get_session_dir(session_id)

            try:
                from stratus.orchestration.spec_state import read_spec_state
                state = read_spec_state(session_dir)
                if state is not None:
                    phase = state.phase
            except ImportError:
                pass

            if phase is None:
                try:
                    from stratus.orchestration.delivery_state import read_delivery_state
                    state = read_delivery_state(session_dir)
                    if state is not None:
                        phase = state.delivery_phase.value
                except (ImportError, AttributeError):
                    pass
        except Exception:
            pass

        msg = evaluate_phase_consistency(subagent_type, phase)
        if msg:
            print(msg, file=sys.stderr)
        sys.exit(0)  # Always informational
    except Exception:
        sys.exit(0)  # Never crash


if __name__ == "__main__":
    main()
