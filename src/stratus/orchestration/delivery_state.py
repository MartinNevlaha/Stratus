"""Delivery state JSON read/write and phase transition validation."""

from __future__ import annotations

import json
from pathlib import Path

from stratus.orchestration.delivery_models import DeliveryPhase, DeliveryState

DELIVERY_TRANSITIONS: dict[DeliveryPhase, set[DeliveryPhase]] = {
    DeliveryPhase.DISCOVERY: {DeliveryPhase.ARCHITECTURE, DeliveryPhase.PLANNING},
    DeliveryPhase.ARCHITECTURE: {DeliveryPhase.PLANNING},
    DeliveryPhase.PLANNING: {DeliveryPhase.IMPLEMENTATION},
    DeliveryPhase.IMPLEMENTATION: {DeliveryPhase.QA},
    DeliveryPhase.QA: {DeliveryPhase.IMPLEMENTATION, DeliveryPhase.GOVERNANCE},
    DeliveryPhase.GOVERNANCE: {
        DeliveryPhase.IMPLEMENTATION,
        DeliveryPhase.PERFORMANCE,
        DeliveryPhase.RELEASE,
    },
    DeliveryPhase.PERFORMANCE: {DeliveryPhase.IMPLEMENTATION, DeliveryPhase.RELEASE},
    DeliveryPhase.RELEASE: {DeliveryPhase.LEARNING},
    DeliveryPhase.LEARNING: set(),
}

# Canonical forward order for determining "next" phase
PHASE_ORDER: list[DeliveryPhase] = list(DeliveryPhase)

_STATE_FILE = "delivery-state.json"


def transition_delivery_phase(current: DeliveryPhase, target: DeliveryPhase) -> DeliveryPhase:
    """Return target phase if the transition is allowed, else raise ValueError."""
    valid = DELIVERY_TRANSITIONS.get(current, set())
    if target not in valid:
        msg = f"Invalid transition: {current} -> {target}. Valid: {valid}"
        raise ValueError(msg)
    return target


def get_next_active_phase(
    current: DeliveryPhase,
    active_phases: set[str],
) -> DeliveryPhase | None:
    """Return the next phase in order that is reachable AND in active_phases.

    Handles transitive skipping: if an intermediate phase is reachable but
    not active, we look through its outgoing edges to find the next active one.
    """
    current_idx = PHASE_ORDER.index(current)
    reachable: set[DeliveryPhase] = DELIVERY_TRANSITIONS[current]

    for phase in PHASE_ORDER[current_idx + 1 :]:
        if phase not in reachable:
            continue
        if phase.value in active_phases:
            return phase
        # Phase is reachable but inactive — pass through its edges
        reachable = reachable | DELIVERY_TRANSITIONS[phase]

    return None


def read_delivery_state(session_dir: Path) -> DeliveryState | None:
    """Read DeliveryState from delivery-state.json. Returns None on missing/corrupt file."""
    path = session_dir / _STATE_FILE
    if not path.exists():
        return None
    try:
        return DeliveryState.model_validate_json(path.read_text())
    except (json.JSONDecodeError, ValueError):
        return None


def write_delivery_state(session_dir: Path, state: DeliveryState) -> None:
    """Write DeliveryState to delivery-state.json, creating parent dirs as needed."""
    path = session_dir / _STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(state.model_dump_json(indent=2))
