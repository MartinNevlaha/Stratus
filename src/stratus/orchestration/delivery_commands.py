"""CLI command handlers for delivery orchestration lifecycle."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from stratus.orchestration.delivery_config import load_delivery_config
from stratus.orchestration.delivery_coordinator import DeliveryCoordinator


def _load_coordinator(session_dir: Path) -> DeliveryCoordinator:
    config = load_delivery_config()
    return DeliveryCoordinator(session_dir=session_dir, config=config)


def cmd_delivery_status(session_dir: Path) -> None:
    """Print current delivery state as JSON."""
    coord = _load_coordinator(session_dir)
    state = coord.get_state()
    if state is None:
        print(json.dumps({"active": False}))
        return
    print(state.model_dump_json(indent=2))


def cmd_delivery_start(
    session_dir: Path,
    slug: str,
    mode: str,
    plan_path: str | None,
) -> None:
    """Start a new delivery lifecycle."""
    config = load_delivery_config()
    config.orchestration_mode = mode
    coord = DeliveryCoordinator(session_dir=session_dir, config=config)
    try:
        state = coord.start_delivery(slug=slug, plan_path=plan_path)
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(state.model_dump_json(indent=2))


def cmd_delivery_advance(session_dir: Path) -> None:
    """Advance to the next active delivery phase."""
    coord = _load_coordinator(session_dir)
    try:
        state = coord.advance_phase()
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(state.model_dump_json(indent=2))


def cmd_delivery_skip(session_dir: Path, reason: str) -> None:
    """Skip the current delivery phase."""
    coord = _load_coordinator(session_dir)
    try:
        state = coord.skip_phase(reason)
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(state.model_dump_json(indent=2))
