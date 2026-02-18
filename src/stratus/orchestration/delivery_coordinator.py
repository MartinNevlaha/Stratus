"""Pure state machine for the 9-phase delivery lifecycle."""

from __future__ import annotations

from pathlib import Path

from stratus.orchestration.delivery_config import DeliveryConfig
from stratus.orchestration.delivery_models import (
    DeliveryPhase,
    DeliveryState,
    OrchestrationMode,
    PhaseResult,
    get_default_phases,
)
from stratus.orchestration.delivery_state import (
    DELIVERY_TRANSITIONS,
    PHASE_ORDER,
    read_delivery_state,
    transition_delivery_phase,
    write_delivery_state,
)

PHASE_ROLES: dict[DeliveryPhase, list[str]] = {
    DeliveryPhase.DISCOVERY: ["product-owner", "tpm", "strategic-architect"],
    DeliveryPhase.ARCHITECTURE: [
        "strategic-architect",
        "system-architect",
        "security-reviewer",
    ],
    DeliveryPhase.PLANNING: ["tpm", "system-architect", "cost-controller"],
    DeliveryPhase.IMPLEMENTATION: [
        "backend-engineer",
        "frontend-engineer",
        "mobile-engineer",
        "devops-engineer",
        "database-engineer",
    ],
    DeliveryPhase.QA: [
        "qa-engineer",
        "code-reviewer",
        "debugger",
        "quality-gate-manager",
    ],
    DeliveryPhase.GOVERNANCE: [
        "risk-officer",
        "security-reviewer",
        "quality-gate-manager",
    ],
    DeliveryPhase.PERFORMANCE: ["performance-engineer", "devops-engineer"],
    DeliveryPhase.RELEASE: [
        "release-manager",
        "devops-engineer",
        "documentation-engineer",
    ],
    DeliveryPhase.LEARNING: ["product-owner", "tpm"],
}

PHASE_LEADS: dict[DeliveryPhase, str] = {
    DeliveryPhase.DISCOVERY: "product-owner",
    DeliveryPhase.ARCHITECTURE: "strategic-architect",
    DeliveryPhase.PLANNING: "tpm",
    DeliveryPhase.IMPLEMENTATION: "tpm",
    DeliveryPhase.QA: "quality-gate-manager",
    DeliveryPhase.GOVERNANCE: "risk-officer",
    DeliveryPhase.PERFORMANCE: "performance-engineer",
    DeliveryPhase.RELEASE: "release-manager",
    DeliveryPhase.LEARNING: "product-owner",
}

_FIX_LOOP_PHASES = {
    DeliveryPhase.QA,
    DeliveryPhase.GOVERNANCE,
    DeliveryPhase.PERFORMANCE,
}


class DeliveryCoordinator:
    """Pure state machine for the 9-phase delivery lifecycle."""

    _session_dir: Path
    _config: DeliveryConfig

    def __init__(self, session_dir: Path, config: DeliveryConfig) -> None:
        self._session_dir = session_dir
        self._config = config
        self._state: DeliveryState | None = read_delivery_state(session_dir)

    def get_state(self) -> DeliveryState | None:
        return self._state

    def set_mode(self, mode: str) -> None:
        """Set orchestration mode before starting delivery."""
        _ = OrchestrationMode(mode)  # validate
        self._config.orchestration_mode = mode

    def _require_state(self) -> DeliveryState:
        if self._state is None:
            raise RuntimeError("No active delivery. Call start_delivery() first.")
        return self._state

    def _active_phases(self) -> set[str]:
        if self._config.active_phases:
            return set(self._config.active_phases)
        mode = OrchestrationMode(self._config.orchestration_mode)
        return {p.value for p in get_default_phases(mode)}

    def _persist(self) -> None:
        if self._state:
            write_delivery_state(self._session_dir, self._state)

    def _find_next_active(self, current: DeliveryPhase, active: set[str]) -> DeliveryPhase | None:
        """Find next reachable phase in active set, skipping inactive phases."""
        current_idx = PHASE_ORDER.index(current)
        reachable: set[DeliveryPhase] = set(DELIVERY_TRANSITIONS[current])

        for phase in PHASE_ORDER[current_idx + 1 :]:
            if phase not in reachable:
                continue
            if phase.value in active:
                return phase
            # Pass through inactive but reachable phase
            reachable = reachable | DELIVERY_TRANSITIONS[phase]

        return None

    def start_delivery(self, slug: str, plan_path: str | None = None) -> DeliveryState:
        """Start a new delivery lifecycle."""
        active = self._active_phases()
        first_phase = next((p for p in PHASE_ORDER if p.value in active), None)
        if first_phase is None:
            raise ValueError("No active phases configured")

        self._state = DeliveryState(
            delivery_phase=first_phase,
            slug=slug,
            orchestration_mode=self._config.orchestration_mode,
            plan_path=plan_path,
            active_roles=PHASE_ROLES.get(first_phase, []),
            phase_lead=PHASE_LEADS.get(first_phase),
            max_review_iterations=self._config.max_review_iterations,
        )
        self._persist()
        return self._state

    def advance_phase(self) -> DeliveryState:
        """Move to the next active phase."""
        state = self._require_state()
        active = self._active_phases()
        next_phase = self._find_next_active(state.delivery_phase, active)
        if next_phase is None:
            raise ValueError(f"No next phase from {state.delivery_phase}")

        # next_phase reachability already validated by _find_next_active;
        # direct-edge check via transition_delivery_phase only applies when no skipping.
        self._state = state.model_copy(
            update={
                "delivery_phase": next_phase,
                "active_roles": PHASE_ROLES.get(next_phase, []),
                "phase_lead": PHASE_LEADS.get(next_phase),
            }
        )
        self._persist()
        return self._state

    def start_fix_loop(self) -> DeliveryState:
        """Transition back to IMPLEMENTATION for a fix iteration."""
        state = self._require_state()
        if state.delivery_phase not in _FIX_LOOP_PHASES:
            raise ValueError(f"Fix loop not available from {state.delivery_phase}")
        if state.review_iteration >= state.max_review_iterations:
            raise ValueError(f"Max review iterations ({state.max_review_iterations}) exceeded")

        _ = transition_delivery_phase(state.delivery_phase, DeliveryPhase.IMPLEMENTATION)
        self._state = state.model_copy(
            update={
                "delivery_phase": DeliveryPhase.IMPLEMENTATION,
                "active_roles": PHASE_ROLES[DeliveryPhase.IMPLEMENTATION],
                "phase_lead": PHASE_LEADS[DeliveryPhase.IMPLEMENTATION],
                "review_iteration": state.review_iteration + 1,
            }
        )
        self._persist()
        return self._state

    def get_active_roles(self) -> list[str]:
        state = self._require_state()
        return PHASE_ROLES.get(state.delivery_phase, [])

    def record_phase_result(self, result: PhaseResult) -> DeliveryState:
        state = self._require_state()
        new_results = dict(state.phase_results)
        new_results[result.phase] = result
        self._state = state.model_copy(update={"phase_results": new_results})
        self._persist()
        return self._state

    def skip_phase(self, reason: str) -> DeliveryState:
        """Record current phase as skipped and advance."""
        state = self._require_state()
        active = self._active_phases()
        next_phase = self._find_next_active(state.delivery_phase, active)
        if next_phase is None:
            raise ValueError(f"No phase to skip to from {state.delivery_phase}")

        skipped = list(state.skipped_phases) + [state.delivery_phase.value]
        new_results = dict(state.phase_results)
        new_results[state.delivery_phase.value] = PhaseResult(
            phase=state.delivery_phase.value, status="skipped", details=reason
        )
        self._state = state.model_copy(
            update={
                "delivery_phase": next_phase,
                "skipped_phases": skipped,
                "phase_results": new_results,
                "active_roles": PHASE_ROLES.get(next_phase, []),
                "phase_lead": PHASE_LEADS.get(next_phase),
            }
        )
        self._persist()
        return self._state

    def complete_delivery(self) -> DeliveryState:
        """Record LEARNING as complete (terminal state)."""
        state = self._require_state()
        if state.delivery_phase != DeliveryPhase.LEARNING:
            raise ValueError(
                f"Can only complete from LEARNING, currently at {state.delivery_phase}"
            )
        new_results = dict(state.phase_results)
        new_results[DeliveryPhase.LEARNING.value] = PhaseResult(
            phase=DeliveryPhase.LEARNING.value, status="passed"
        )
        self._state = state.model_copy(update={"phase_results": new_results})
        self._persist()
        return self._state

    def get_next_phase(self) -> DeliveryPhase | None:
        """Peek at the next phase without mutating state."""
        state = self._require_state()
        return self._find_next_active(state.delivery_phase, self._active_phases())
