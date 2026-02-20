"""Tests for delivery_coordinator.py — DeliveryCoordinator state machine."""

from __future__ import annotations

from pathlib import Path

import pytest

from stratus.orchestration.delivery_config import DeliveryConfig
from stratus.orchestration.delivery_models import (
    DEFAULT_ACTIVE_PHASES,
    DeliveryPhase,
    DeliveryState,
    OrchestrationMode,
    PhaseResult,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def session_dir(tmp_path: Path) -> Path:
    d = tmp_path / "sessions" / "test-session"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def classic_config() -> DeliveryConfig:
    phases = [p.value for p in DEFAULT_ACTIVE_PHASES[OrchestrationMode.CLASSIC]]
    return DeliveryConfig(
        orchestration_mode="classic",
        max_review_iterations=3,
        active_phases=phases,
    )


@pytest.fixture
def swarm_config() -> DeliveryConfig:
    phases = [p.value for p in DEFAULT_ACTIVE_PHASES[OrchestrationMode.SWARM]]
    return DeliveryConfig(
        orchestration_mode="swarm",
        max_review_iterations=3,
        active_phases=phases,
    )


@pytest.fixture
def classic_coordinator(session_dir: Path, classic_config: DeliveryConfig):
    from stratus.orchestration.delivery_coordinator import DeliveryCoordinator

    return DeliveryCoordinator(session_dir, classic_config)


@pytest.fixture
def swarm_coordinator(session_dir: Path, swarm_config: DeliveryConfig):
    from stratus.orchestration.delivery_coordinator import DeliveryCoordinator

    return DeliveryCoordinator(session_dir, swarm_config)


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_accepts_session_dir_and_config(
        self, session_dir: Path, classic_config: DeliveryConfig
    ):
        from stratus.orchestration.delivery_coordinator import DeliveryCoordinator

        coord = DeliveryCoordinator(session_dir, classic_config)
        assert coord.get_state() is None

    def test_loads_existing_state_from_disk(
        self, session_dir: Path, classic_config: DeliveryConfig
    ):
        from stratus.orchestration.delivery_coordinator import DeliveryCoordinator
        from stratus.orchestration.delivery_state import write_delivery_state

        state = DeliveryState(delivery_phase=DeliveryPhase.QA, slug="existing")
        write_delivery_state(session_dir, state)

        coord = DeliveryCoordinator(session_dir, classic_config)
        loaded = coord.get_state()
        assert loaded is not None
        assert loaded.slug == "existing"
        assert loaded.delivery_phase == DeliveryPhase.QA


# ---------------------------------------------------------------------------
# start_delivery
# ---------------------------------------------------------------------------


class TestStartDelivery:
    def test_classic_starts_at_implementation(self, classic_coordinator):
        state = classic_coordinator.start_delivery("my-feature")
        assert state.delivery_phase == DeliveryPhase.IMPLEMENTATION

    def test_swarm_starts_at_discovery(self, swarm_coordinator):
        state = swarm_coordinator.start_delivery("my-feature")
        assert state.delivery_phase == DeliveryPhase.DISCOVERY

    def test_sets_slug(self, classic_coordinator):
        state = classic_coordinator.start_delivery("cool-slug")
        assert state.slug == "cool-slug"

    def test_sets_plan_path_when_provided(self, classic_coordinator):
        state = classic_coordinator.start_delivery("feat", plan_path="/tmp/plan.md")
        assert state.plan_path == "/tmp/plan.md"

    def test_sets_orchestration_mode(self, classic_coordinator):
        state = classic_coordinator.start_delivery("feat")
        assert state.orchestration_mode == "classic"

    def test_sets_active_roles_for_starting_phase(self, classic_coordinator):
        from stratus.orchestration.delivery_coordinator import PHASE_ROLES

        state = classic_coordinator.start_delivery("feat")
        expected = PHASE_ROLES[DeliveryPhase.IMPLEMENTATION]
        assert state.active_roles == expected

    def test_sets_phase_lead_for_starting_phase(self, classic_coordinator):
        from stratus.orchestration.delivery_coordinator import PHASE_LEADS

        state = classic_coordinator.start_delivery("feat")
        assert state.phase_lead == PHASE_LEADS[DeliveryPhase.IMPLEMENTATION]

    def test_persists_state_to_disk(self, classic_coordinator, session_dir: Path):
        classic_coordinator.start_delivery("feat")
        assert (session_dir / "delivery-state.json").exists()

    def test_custom_active_phases_respected(self, session_dir: Path):
        from stratus.orchestration.delivery_coordinator import DeliveryCoordinator

        config = DeliveryConfig(
            orchestration_mode="classic",
            active_phases=["planning", "implementation", "qa", "release", "learning"],
        )
        coord = DeliveryCoordinator(session_dir, config)
        state = coord.start_delivery("feat")
        assert state.delivery_phase == DeliveryPhase.PLANNING

    def test_raises_when_no_active_phases(self, session_dir: Path):
        from stratus.orchestration.delivery_coordinator import DeliveryCoordinator

        config = DeliveryConfig(orchestration_mode="classic", active_phases=["bogus-phase"])
        coord = DeliveryCoordinator(session_dir, config)
        with pytest.raises(ValueError, match="No active phases"):
            coord.start_delivery("feat")


# ---------------------------------------------------------------------------
# advance_phase
# ---------------------------------------------------------------------------


class TestAdvancePhase:
    def test_advances_to_next_phase(self, classic_coordinator):
        classic_coordinator.start_delivery("feat")
        # Classic starts at IMPLEMENTATION; advance to QA
        state = classic_coordinator.advance_phase()
        assert state.delivery_phase == DeliveryPhase.QA

    def test_updates_active_roles(self, classic_coordinator):
        from stratus.orchestration.delivery_coordinator import PHASE_ROLES

        classic_coordinator.start_delivery("feat")
        state = classic_coordinator.advance_phase()
        assert state.active_roles == PHASE_ROLES[DeliveryPhase.QA]

    def test_updates_phase_lead(self, classic_coordinator):
        from stratus.orchestration.delivery_coordinator import PHASE_LEADS

        classic_coordinator.start_delivery("feat")
        state = classic_coordinator.advance_phase()
        assert state.phase_lead == PHASE_LEADS[DeliveryPhase.QA]

    def test_persists_after_advance(self, classic_coordinator, session_dir: Path):
        from stratus.orchestration.delivery_state import read_delivery_state

        classic_coordinator.start_delivery("feat")
        classic_coordinator.advance_phase()
        persisted = read_delivery_state(session_dir)
        assert persisted is not None
        assert persisted.delivery_phase == DeliveryPhase.QA

    def test_skips_disabled_phases(self, session_dir: Path):
        from stratus.orchestration.delivery_coordinator import DeliveryCoordinator

        # Active: implementation, governance, release, learning (QA skipped)
        config = DeliveryConfig(
            orchestration_mode="classic",
            active_phases=["implementation", "governance", "release", "learning"],
        )
        coord = DeliveryCoordinator(session_dir, config)
        coord.start_delivery("feat")
        # starts at IMPLEMENTATION; advance should skip QA and go to GOVERNANCE
        state = coord.advance_phase()
        assert state.delivery_phase == DeliveryPhase.GOVERNANCE

    def test_raises_at_terminal_phase(self, session_dir: Path):
        from stratus.orchestration.delivery_coordinator import DeliveryCoordinator
        from stratus.orchestration.delivery_state import write_delivery_state

        phases = [p.value for p in DEFAULT_ACTIVE_PHASES[OrchestrationMode.CLASSIC]]
        config = DeliveryConfig(orchestration_mode="classic", active_phases=phases)
        coord = DeliveryCoordinator(session_dir, config)
        # Manually put coordinator in LEARNING (terminal)
        state = DeliveryState(delivery_phase=DeliveryPhase.LEARNING, slug="feat")
        write_delivery_state(session_dir, state)
        coord._state = state  # noqa: SLF001

        with pytest.raises(ValueError):
            coord.advance_phase()

    def test_raises_without_active_delivery(self, classic_coordinator):
        with pytest.raises(RuntimeError, match="No active delivery"):
            classic_coordinator.advance_phase()


# ---------------------------------------------------------------------------
# start_fix_loop
# ---------------------------------------------------------------------------


class TestStartFixLoop:
    def _advance_to_qa(self, coord):
        coord.start_delivery("feat")
        coord.advance_phase()  # IMPLEMENTATION -> QA

    def _advance_to_governance(self, coord):
        self._advance_to_qa(coord)
        coord.advance_phase()  # QA -> GOVERNANCE

    def test_transitions_from_qa_to_implementation(self, classic_coordinator):
        self._advance_to_qa(classic_coordinator)
        state = classic_coordinator.start_fix_loop()
        assert state.delivery_phase == DeliveryPhase.IMPLEMENTATION

    def test_transitions_from_governance_to_implementation(self, session_dir: Path):
        from stratus.orchestration.delivery_coordinator import DeliveryCoordinator

        config = DeliveryConfig(
            orchestration_mode="classic",
            active_phases=["implementation", "qa", "governance", "release", "learning"],
        )
        coord = DeliveryCoordinator(session_dir, config)
        self._advance_to_governance(coord)
        state = coord.start_fix_loop()
        assert state.delivery_phase == DeliveryPhase.IMPLEMENTATION

    def test_increments_review_iteration(self, classic_coordinator):
        self._advance_to_qa(classic_coordinator)
        state = classic_coordinator.start_fix_loop()
        assert state.review_iteration == 1

    def test_fix_loop_increments_on_each_call(self, classic_coordinator):
        self._advance_to_qa(classic_coordinator)
        classic_coordinator.start_fix_loop()
        classic_coordinator.advance_phase()  # back to QA
        state = classic_coordinator.start_fix_loop()
        assert state.review_iteration == 2

    def test_raises_from_non_fixable_phase(self, classic_coordinator):
        classic_coordinator.start_delivery("feat")  # IMPLEMENTATION
        with pytest.raises(ValueError, match="Fix loop not available"):
            classic_coordinator.start_fix_loop()

    def test_raises_from_discovery_phase(self, swarm_coordinator):
        swarm_coordinator.start_delivery("feat")  # DISCOVERY
        with pytest.raises(ValueError, match="Fix loop not available"):
            swarm_coordinator.start_fix_loop()

    def test_raises_when_max_iterations_exceeded(self, session_dir: Path):
        from stratus.orchestration.delivery_coordinator import DeliveryCoordinator

        config = DeliveryConfig(
            orchestration_mode="classic",
            active_phases=["implementation", "qa", "governance", "release", "learning"],
            max_review_iterations=2,
        )
        coord = DeliveryCoordinator(session_dir, config)
        coord.start_delivery("feat")
        coord.advance_phase()  # -> QA

        coord.start_fix_loop()  # iteration 1
        coord.advance_phase()  # back to QA
        coord.start_fix_loop()  # iteration 2

        coord.advance_phase()  # back to QA again
        with pytest.raises(ValueError, match="Max review iterations"):
            coord.start_fix_loop()

    def test_persists_after_fix_loop(self, classic_coordinator, session_dir: Path):
        from stratus.orchestration.delivery_state import read_delivery_state

        self._advance_to_qa(classic_coordinator)
        classic_coordinator.start_fix_loop()
        persisted = read_delivery_state(session_dir)
        assert persisted is not None
        assert persisted.delivery_phase == DeliveryPhase.IMPLEMENTATION
        assert persisted.review_iteration == 1

    def test_raises_without_active_delivery(self, classic_coordinator):
        with pytest.raises(RuntimeError, match="No active delivery"):
            classic_coordinator.start_fix_loop()


# ---------------------------------------------------------------------------
# get_active_roles
# ---------------------------------------------------------------------------


class TestGetActiveRoles:
    def test_returns_roles_for_current_phase(self, classic_coordinator):
        from stratus.orchestration.delivery_coordinator import PHASE_ROLES

        classic_coordinator.start_delivery("feat")
        roles = classic_coordinator.get_active_roles()
        assert roles == PHASE_ROLES[DeliveryPhase.IMPLEMENTATION]

    def test_returns_roles_after_advance(self, classic_coordinator):
        from stratus.orchestration.delivery_coordinator import PHASE_ROLES

        classic_coordinator.start_delivery("feat")
        classic_coordinator.advance_phase()  # -> QA
        roles = classic_coordinator.get_active_roles()
        assert roles == PHASE_ROLES[DeliveryPhase.QA]

    def test_raises_without_active_delivery(self, classic_coordinator):
        with pytest.raises(RuntimeError, match="No active delivery"):
            classic_coordinator.get_active_roles()


# ---------------------------------------------------------------------------
# record_phase_result
# ---------------------------------------------------------------------------


class TestRecordPhaseResult:
    def test_stores_result_in_state(self, classic_coordinator):
        classic_coordinator.start_delivery("feat")
        result = PhaseResult(phase="implementation", status="passed")
        state = classic_coordinator.record_phase_result(result)
        assert "implementation" in state.phase_results
        assert state.phase_results["implementation"].status == "passed"

    def test_persists_result(self, classic_coordinator, session_dir: Path):
        from stratus.orchestration.delivery_state import read_delivery_state

        classic_coordinator.start_delivery("feat")
        result = PhaseResult(phase="implementation", status="passed")
        classic_coordinator.record_phase_result(result)
        persisted = read_delivery_state(session_dir)
        assert persisted is not None
        assert "implementation" in persisted.phase_results

    def test_overwrites_existing_result(self, classic_coordinator):
        classic_coordinator.start_delivery("feat")
        r1 = PhaseResult(phase="implementation", status="failed")
        classic_coordinator.record_phase_result(r1)
        r2 = PhaseResult(phase="implementation", status="passed")
        state = classic_coordinator.record_phase_result(r2)
        assert state.phase_results["implementation"].status == "passed"

    def test_raises_without_active_delivery(self, classic_coordinator):
        with pytest.raises(RuntimeError, match="No active delivery"):
            classic_coordinator.record_phase_result(
                PhaseResult(phase="implementation", status="passed")
            )


# ---------------------------------------------------------------------------
# skip_phase
# ---------------------------------------------------------------------------


class TestSkipPhase:
    def test_records_skip_reason(self, classic_coordinator):
        classic_coordinator.start_delivery("feat")
        classic_coordinator.advance_phase()  # -> QA
        state = classic_coordinator.skip_phase("Not needed for MVP")
        assert "qa" in state.skipped_phases

    def test_advances_to_next_phase_after_skip(self, classic_coordinator):
        classic_coordinator.start_delivery("feat")
        classic_coordinator.advance_phase()  # -> QA
        state = classic_coordinator.skip_phase("fast track")
        assert state.delivery_phase == DeliveryPhase.GOVERNANCE

    def test_records_skip_in_phase_results(self, classic_coordinator):
        classic_coordinator.start_delivery("feat")
        classic_coordinator.advance_phase()  # -> QA
        state = classic_coordinator.skip_phase("reason")
        assert "qa" in state.phase_results
        assert state.phase_results["qa"].status == "skipped"

    def test_persists_after_skip(self, classic_coordinator, session_dir: Path):
        from stratus.orchestration.delivery_state import read_delivery_state

        classic_coordinator.start_delivery("feat")
        classic_coordinator.advance_phase()  # -> QA
        classic_coordinator.skip_phase("reason")
        persisted = read_delivery_state(session_dir)
        assert persisted is not None
        assert "qa" in persisted.skipped_phases

    def test_raises_without_active_delivery(self, classic_coordinator):
        with pytest.raises(RuntimeError, match="No active delivery"):
            classic_coordinator.skip_phase("no delivery")


# ---------------------------------------------------------------------------
# complete_delivery
# ---------------------------------------------------------------------------


class TestCompleteDelivery:
    def _advance_to_learning(self, coord):
        """Drive classic coordinator to LEARNING phase."""
        coord.start_delivery("feat")
        coord.advance_phase()  # IMPL -> QA
        coord.advance_phase()  # QA -> GOVERNANCE
        coord.advance_phase()  # GOVERNANCE -> RELEASE
        coord.advance_phase()  # RELEASE -> LEARNING

    def test_completes_from_learning_phase(self, classic_coordinator):
        self._advance_to_learning(classic_coordinator)
        state = classic_coordinator.complete_delivery()
        assert state.delivery_phase == DeliveryPhase.LEARNING
        assert "learning" in state.phase_results

    def test_records_learning_result_as_passed(self, classic_coordinator):
        self._advance_to_learning(classic_coordinator)
        state = classic_coordinator.complete_delivery()
        assert state.phase_results["learning"].status == "passed"

    def test_persists_completion(self, classic_coordinator, session_dir: Path):
        from stratus.orchestration.delivery_state import read_delivery_state

        self._advance_to_learning(classic_coordinator)
        classic_coordinator.complete_delivery()
        persisted = read_delivery_state(session_dir)
        assert persisted is not None
        assert "learning" in persisted.phase_results

    def test_raises_if_not_at_learning(self, classic_coordinator):
        classic_coordinator.start_delivery("feat")
        with pytest.raises(ValueError, match="LEARNING"):
            classic_coordinator.complete_delivery()

    def test_raises_without_active_delivery(self, classic_coordinator):
        with pytest.raises(RuntimeError, match="No active delivery"):
            classic_coordinator.complete_delivery()


# ---------------------------------------------------------------------------
# get_next_phase (peek)
# ---------------------------------------------------------------------------


class TestGetNextPhase:
    def test_peeks_without_mutating(self, classic_coordinator):
        classic_coordinator.start_delivery("feat")
        next_p = classic_coordinator.get_next_phase()
        assert next_p == DeliveryPhase.QA
        # State must not have changed
        assert classic_coordinator.get_state().delivery_phase == DeliveryPhase.IMPLEMENTATION  # type: ignore[union-attr]

    def test_returns_none_at_terminal(self, session_dir: Path):
        from stratus.orchestration.delivery_coordinator import DeliveryCoordinator
        from stratus.orchestration.delivery_state import write_delivery_state

        phases = [p.value for p in DEFAULT_ACTIVE_PHASES[OrchestrationMode.CLASSIC]]
        config = DeliveryConfig(orchestration_mode="classic", active_phases=phases)
        coord = DeliveryCoordinator(session_dir, config)
        state = DeliveryState(delivery_phase=DeliveryPhase.LEARNING, slug="feat")
        write_delivery_state(session_dir, state)
        coord._state = state  # noqa: SLF001

        assert coord.get_next_phase() is None

    def test_raises_without_active_delivery(self, classic_coordinator):
        with pytest.raises(RuntimeError, match="No active delivery"):
            classic_coordinator.get_next_phase()


# ---------------------------------------------------------------------------
# PHASE_ROLES mapping
# ---------------------------------------------------------------------------


class TestPhaseRoles:
    def test_all_phases_have_roles(self):
        from stratus.orchestration.delivery_coordinator import PHASE_ROLES

        for phase in DeliveryPhase:
            assert phase in PHASE_ROLES
            assert len(PHASE_ROLES[phase]) > 0

    def test_implementation_has_engineer_roles(self):
        from stratus.orchestration.delivery_coordinator import PHASE_ROLES

        roles = PHASE_ROLES[DeliveryPhase.IMPLEMENTATION]
        assert any("engineer" in r for r in roles)

    def test_qa_has_qa_engineer(self):
        from stratus.orchestration.delivery_coordinator import PHASE_ROLES

        assert "qa-engineer" in PHASE_ROLES[DeliveryPhase.QA]

    def test_governance_has_risk_officer(self):
        from stratus.orchestration.delivery_coordinator import PHASE_ROLES

        assert "risk-officer" in PHASE_ROLES[DeliveryPhase.GOVERNANCE]

    def test_release_has_release_manager(self):
        from stratus.orchestration.delivery_coordinator import PHASE_ROLES

        assert "release-manager" in PHASE_ROLES[DeliveryPhase.RELEASE]


# ---------------------------------------------------------------------------
# State persistence — every mutation persists
# ---------------------------------------------------------------------------


class TestStatePersistence:
    def test_state_persisted_after_start_delivery(self, classic_coordinator, session_dir: Path):
        from stratus.orchestration.delivery_state import read_delivery_state

        classic_coordinator.start_delivery("feat")
        assert read_delivery_state(session_dir) is not None

    def test_state_persisted_after_advance_phase(self, classic_coordinator, session_dir: Path):
        from stratus.orchestration.delivery_state import read_delivery_state

        classic_coordinator.start_delivery("feat")
        classic_coordinator.advance_phase()
        persisted = read_delivery_state(session_dir)
        assert persisted is not None
        assert persisted.delivery_phase == DeliveryPhase.QA

    def test_state_persisted_after_record_phase_result(
        self, classic_coordinator, session_dir: Path
    ):
        from stratus.orchestration.delivery_state import read_delivery_state

        classic_coordinator.start_delivery("feat")
        classic_coordinator.record_phase_result(
            PhaseResult(phase="implementation", status="passed")
        )
        persisted = read_delivery_state(session_dir)
        assert persisted is not None
        assert "implementation" in persisted.phase_results
