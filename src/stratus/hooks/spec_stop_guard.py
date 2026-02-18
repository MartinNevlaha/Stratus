"""Stop hook: block exit during active /spec verify phase or active delivery phases."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

STALE_HOURS = 4

# Delivery phases that should block exit
_BLOCKING_DELIVERY_PHASES = {"implementation", "qa"}


def _check_delivery_active(session_dir: Path) -> bool:
    """Return True if delivery is active in a blocking phase (not stale)."""
    try:
        from stratus.orchestration.delivery_state import read_delivery_state

        state = read_delivery_state(session_dir)
        if state is None:
            return False
        if state.delivery_phase.value not in _BLOCKING_DELIVERY_PHASES:
            return False
        # Staleness check
        try:
            ts = datetime.fromisoformat(state.last_updated)
            age = (datetime.now(UTC) - ts).total_seconds() / 3600
            if age > STALE_HOURS:
                return False
        except (ValueError, TypeError):
            pass
        return True
    except ImportError:
        return False


def main() -> None:
    """Entry point for Stop hook."""

    from stratus.hooks._common import get_session_dir
    from stratus.orchestration.spec_state import is_verify_active, read_spec_state
    from stratus.session.state import resolve_session_id

    session_id = resolve_session_id()
    session_dir = get_session_dir(session_id)

    # Check spec verify phase
    if is_verify_active(session_dir):
        state = read_spec_state(session_dir)
        if state and state.last_updated:
            try:
                ts = datetime.fromisoformat(state.last_updated)
                age = (datetime.now(UTC) - ts).total_seconds() / 3600
                if age > STALE_HOURS:
                    sys.exit(0)
            except (ValueError, TypeError):
                pass
        print(
            "Spec verification is in progress. Complete or cancel before exiting.",
            file=sys.stderr,
        )
        sys.exit(2)

    # Check delivery blocking phases
    if _check_delivery_active(session_dir):
        print(
            "Delivery is active (implementation/QA phase). Complete or cancel before exiting.",
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
