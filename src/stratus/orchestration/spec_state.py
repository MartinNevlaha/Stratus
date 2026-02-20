"""Spec state JSON read/write, phase transitions, and convenience predicates."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from stratus.orchestration.models import SpecPhase, SpecState

_SPEC_STATE_FILE = "spec-state.json"

VALID_TRANSITIONS: dict[SpecPhase, set[SpecPhase]] = {
    SpecPhase.PLAN: {SpecPhase.IMPLEMENT, SpecPhase.ACCEPT},
    SpecPhase.DISCOVERY: {SpecPhase.DESIGN},
    SpecPhase.DESIGN: {SpecPhase.GOVERNANCE, SpecPhase.PLAN},
    SpecPhase.GOVERNANCE: {SpecPhase.PLAN},
    SpecPhase.ACCEPT: {SpecPhase.IMPLEMENT},
    SpecPhase.IMPLEMENT: {SpecPhase.VERIFY},
    SpecPhase.VERIFY: {SpecPhase.IMPLEMENT, SpecPhase.LEARN},
    SpecPhase.LEARN: set(),
}


def read_spec_state(session_dir: Path) -> SpecState | None:
    """Read SpecState from spec-state.json. Returns None on missing or corrupt file."""
    path = session_dir / _SPEC_STATE_FILE
    try:
        data = json.loads(path.read_text())
        return SpecState(**data)
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError, ValueError):
        return None


def write_spec_state(session_dir: Path, state: SpecState) -> None:
    """Write SpecState to spec-state.json atomically, creating parent dirs as needed."""
    path = session_dir / _SPEC_STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(state.model_dump(), indent=2)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.write(fd, content.encode())
        os.close(fd)
        os.replace(tmp, path)
    except BaseException:
        os.close(fd)
        os.unlink(tmp)
        raise


def transition_phase(state: SpecState, new_phase: SpecPhase) -> SpecState:
    """Return a new SpecState with the given phase, validating the transition.

    Raises ValueError if the transition from the current phase to new_phase
    is not in VALID_TRANSITIONS.
    """
    allowed = VALID_TRANSITIONS[state.phase]
    if new_phase not in allowed:
        raise ValueError(
            f"Invalid phase transition: {state.phase!r} -> {new_phase!r}. "
            f"Allowed from {state.phase!r}: {sorted(p.value for p in allowed) or 'none'}"
        )
    return state.model_copy(update={"phase": new_phase})


def is_spec_active(session_dir: Path) -> bool:
    """Return True if a spec is in progress (phase is not learn and file exists)."""
    state = read_spec_state(session_dir)
    if state is None:
        return False
    return state.phase != SpecPhase.LEARN


def is_verify_active(session_dir: Path) -> bool:
    """Return True if the current spec phase is verify."""
    state = read_spec_state(session_dir)
    if state is None:
        return False
    return state.phase == SpecPhase.VERIFY


def mark_task_complete(state: SpecState, task_num: int) -> SpecState:
    """Return updated SpecState with completed_tasks incremented and current_task advanced."""
    new_completed = state.completed_tasks + 1
    new_current = min(state.current_task + 1, state.total_tasks)
    return state.model_copy(update={"completed_tasks": new_completed, "current_task": new_current})
