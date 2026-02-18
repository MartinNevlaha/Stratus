"""Tests for delivery_state.py — DELIVERY_TRANSITIONS, transition_delivery_phase, read/write."""

from __future__ import annotations

import json

import pytest

from stratus.orchestration.delivery_models import DeliveryPhase, DeliveryState

# ---------------------------------------------------------------------------
# DELIVERY_TRANSITIONS structure
# ---------------------------------------------------------------------------


class TestDeliveryTransitionsStructure:
    def test_maps_all_9_delivery_phases(self):
        from stratus.orchestration.delivery_state import DELIVERY_TRANSITIONS

        assert set(DELIVERY_TRANSITIONS.keys()) == set(DeliveryPhase)

    def test_discovery_can_go_to_architecture(self):
        from stratus.orchestration.delivery_state import DELIVERY_TRANSITIONS

        assert DeliveryPhase.ARCHITECTURE in DELIVERY_TRANSITIONS[DeliveryPhase.DISCOVERY]

    def test_discovery_can_go_to_planning(self):
        from stratus.orchestration.delivery_state import DELIVERY_TRANSITIONS

        assert DeliveryPhase.PLANNING in DELIVERY_TRANSITIONS[DeliveryPhase.DISCOVERY]

    def test_architecture_can_only_go_to_planning(self):
        from stratus.orchestration.delivery_state import DELIVERY_TRANSITIONS

        assert DELIVERY_TRANSITIONS[DeliveryPhase.ARCHITECTURE] == {DeliveryPhase.PLANNING}

    def test_planning_can_only_go_to_implementation(self):
        from stratus.orchestration.delivery_state import DELIVERY_TRANSITIONS

        assert DELIVERY_TRANSITIONS[DeliveryPhase.PLANNING] == {DeliveryPhase.IMPLEMENTATION}

    def test_implementation_can_only_go_to_qa(self):
        from stratus.orchestration.delivery_state import DELIVERY_TRANSITIONS

        assert DELIVERY_TRANSITIONS[DeliveryPhase.IMPLEMENTATION] == {DeliveryPhase.QA}

    def test_qa_can_go_to_implementation_fix_loop(self):
        from stratus.orchestration.delivery_state import DELIVERY_TRANSITIONS

        assert DeliveryPhase.IMPLEMENTATION in DELIVERY_TRANSITIONS[DeliveryPhase.QA]

    def test_qa_can_go_to_governance(self):
        from stratus.orchestration.delivery_state import DELIVERY_TRANSITIONS

        assert DeliveryPhase.GOVERNANCE in DELIVERY_TRANSITIONS[DeliveryPhase.QA]

    def test_governance_can_go_to_implementation(self):
        from stratus.orchestration.delivery_state import DELIVERY_TRANSITIONS

        assert DeliveryPhase.IMPLEMENTATION in DELIVERY_TRANSITIONS[DeliveryPhase.GOVERNANCE]

    def test_governance_can_go_to_performance(self):
        from stratus.orchestration.delivery_state import DELIVERY_TRANSITIONS

        assert DeliveryPhase.PERFORMANCE in DELIVERY_TRANSITIONS[DeliveryPhase.GOVERNANCE]

    def test_governance_can_go_to_release(self):
        from stratus.orchestration.delivery_state import DELIVERY_TRANSITIONS

        assert DeliveryPhase.RELEASE in DELIVERY_TRANSITIONS[DeliveryPhase.GOVERNANCE]

    def test_performance_can_go_to_implementation(self):
        from stratus.orchestration.delivery_state import DELIVERY_TRANSITIONS

        assert DeliveryPhase.IMPLEMENTATION in DELIVERY_TRANSITIONS[DeliveryPhase.PERFORMANCE]

    def test_performance_can_go_to_release(self):
        from stratus.orchestration.delivery_state import DELIVERY_TRANSITIONS

        assert DeliveryPhase.RELEASE in DELIVERY_TRANSITIONS[DeliveryPhase.PERFORMANCE]

    def test_release_can_only_go_to_learning(self):
        from stratus.orchestration.delivery_state import DELIVERY_TRANSITIONS

        assert DELIVERY_TRANSITIONS[DeliveryPhase.RELEASE] == {DeliveryPhase.LEARNING}

    def test_learning_has_no_transitions(self):
        from stratus.orchestration.delivery_state import DELIVERY_TRANSITIONS

        assert DELIVERY_TRANSITIONS[DeliveryPhase.LEARNING] == set()


# ---------------------------------------------------------------------------
# transition_delivery_phase
# ---------------------------------------------------------------------------


class TestTransitionDeliveryPhase:
    def test_valid_discovery_to_architecture(self):
        from stratus.orchestration.delivery_state import transition_delivery_phase

        result = transition_delivery_phase(DeliveryPhase.DISCOVERY, DeliveryPhase.ARCHITECTURE)
        assert result == DeliveryPhase.ARCHITECTURE

    def test_valid_discovery_to_planning(self):
        from stratus.orchestration.delivery_state import transition_delivery_phase

        result = transition_delivery_phase(DeliveryPhase.DISCOVERY, DeliveryPhase.PLANNING)
        assert result == DeliveryPhase.PLANNING

    def test_valid_architecture_to_planning(self):
        from stratus.orchestration.delivery_state import transition_delivery_phase

        result = transition_delivery_phase(DeliveryPhase.ARCHITECTURE, DeliveryPhase.PLANNING)
        assert result == DeliveryPhase.PLANNING

    def test_valid_planning_to_implementation(self):
        from stratus.orchestration.delivery_state import transition_delivery_phase

        result = transition_delivery_phase(DeliveryPhase.PLANNING, DeliveryPhase.IMPLEMENTATION)
        assert result == DeliveryPhase.IMPLEMENTATION

    def test_valid_implementation_to_qa(self):
        from stratus.orchestration.delivery_state import transition_delivery_phase

        result = transition_delivery_phase(DeliveryPhase.IMPLEMENTATION, DeliveryPhase.QA)
        assert result == DeliveryPhase.QA

    def test_valid_qa_to_implementation_fix_loop(self):
        from stratus.orchestration.delivery_state import transition_delivery_phase

        result = transition_delivery_phase(DeliveryPhase.QA, DeliveryPhase.IMPLEMENTATION)
        assert result == DeliveryPhase.IMPLEMENTATION

    def test_valid_qa_to_governance(self):
        from stratus.orchestration.delivery_state import transition_delivery_phase

        result = transition_delivery_phase(DeliveryPhase.QA, DeliveryPhase.GOVERNANCE)
        assert result == DeliveryPhase.GOVERNANCE

    def test_valid_governance_to_release(self):
        from stratus.orchestration.delivery_state import transition_delivery_phase

        result = transition_delivery_phase(DeliveryPhase.GOVERNANCE, DeliveryPhase.RELEASE)
        assert result == DeliveryPhase.RELEASE

    def test_valid_governance_to_performance(self):
        from stratus.orchestration.delivery_state import transition_delivery_phase

        result = transition_delivery_phase(DeliveryPhase.GOVERNANCE, DeliveryPhase.PERFORMANCE)
        assert result == DeliveryPhase.PERFORMANCE

    def test_valid_governance_to_implementation(self):
        from stratus.orchestration.delivery_state import transition_delivery_phase

        result = transition_delivery_phase(DeliveryPhase.GOVERNANCE, DeliveryPhase.IMPLEMENTATION)
        assert result == DeliveryPhase.IMPLEMENTATION

    def test_valid_performance_to_release(self):
        from stratus.orchestration.delivery_state import transition_delivery_phase

        result = transition_delivery_phase(DeliveryPhase.PERFORMANCE, DeliveryPhase.RELEASE)
        assert result == DeliveryPhase.RELEASE

    def test_valid_performance_to_implementation(self):
        from stratus.orchestration.delivery_state import transition_delivery_phase

        result = transition_delivery_phase(DeliveryPhase.PERFORMANCE, DeliveryPhase.IMPLEMENTATION)
        assert result == DeliveryPhase.IMPLEMENTATION

    def test_valid_release_to_learning(self):
        from stratus.orchestration.delivery_state import transition_delivery_phase

        result = transition_delivery_phase(DeliveryPhase.RELEASE, DeliveryPhase.LEARNING)
        assert result == DeliveryPhase.LEARNING

    def test_invalid_discovery_to_implementation(self):
        from stratus.orchestration.delivery_state import transition_delivery_phase

        with pytest.raises(ValueError, match="Invalid transition"):
            transition_delivery_phase(DeliveryPhase.DISCOVERY, DeliveryPhase.IMPLEMENTATION)

    def test_invalid_architecture_to_implementation(self):
        from stratus.orchestration.delivery_state import transition_delivery_phase

        with pytest.raises(ValueError):
            transition_delivery_phase(DeliveryPhase.ARCHITECTURE, DeliveryPhase.IMPLEMENTATION)

    def test_invalid_planning_to_qa(self):
        from stratus.orchestration.delivery_state import transition_delivery_phase

        with pytest.raises(ValueError):
            transition_delivery_phase(DeliveryPhase.PLANNING, DeliveryPhase.QA)

    def test_invalid_implementation_to_governance(self):
        from stratus.orchestration.delivery_state import transition_delivery_phase

        with pytest.raises(ValueError):
            transition_delivery_phase(DeliveryPhase.IMPLEMENTATION, DeliveryPhase.GOVERNANCE)

    def test_invalid_learning_to_any(self):
        from stratus.orchestration.delivery_state import transition_delivery_phase

        for phase in DeliveryPhase:
            if phase == DeliveryPhase.LEARNING:
                continue
            with pytest.raises(ValueError):
                transition_delivery_phase(DeliveryPhase.LEARNING, phase)

    def test_returns_target_phase_on_success(self):
        from stratus.orchestration.delivery_state import transition_delivery_phase

        result = transition_delivery_phase(DeliveryPhase.QA, DeliveryPhase.GOVERNANCE)
        assert result is DeliveryPhase.GOVERNANCE


# ---------------------------------------------------------------------------
# read_delivery_state / write_delivery_state
# ---------------------------------------------------------------------------


class TestReadDeliveryState:
    def test_returns_none_when_file_missing(self, tmp_path):
        from stratus.orchestration.delivery_state import read_delivery_state

        assert read_delivery_state(tmp_path) is None

    def test_returns_none_for_invalid_json(self, tmp_path):
        from stratus.orchestration.delivery_state import read_delivery_state

        (tmp_path / "delivery-state.json").write_text("{ invalid }")
        assert read_delivery_state(tmp_path) is None

    def test_reads_valid_state(self, tmp_path):
        from stratus.orchestration.delivery_state import (
            read_delivery_state,
            write_delivery_state,
        )

        state = DeliveryState(delivery_phase=DeliveryPhase.QA, slug="test-slug")
        write_delivery_state(tmp_path, state)
        result = read_delivery_state(tmp_path)
        assert result is not None
        assert result.delivery_phase == DeliveryPhase.QA
        assert result.slug == "test-slug"

    def test_preserves_all_fields(self, tmp_path):
        from stratus.orchestration.delivery_models import PhaseResult
        from stratus.orchestration.delivery_state import (
            read_delivery_state,
            write_delivery_state,
        )

        state = DeliveryState(
            delivery_phase=DeliveryPhase.GOVERNANCE,
            slug="full-test",
            orchestration_mode="swarm",
            active_roles=["risk-officer"],
            phase_lead="risk-officer",
            skipped_phases=["performance"],
            phase_results={"qa": PhaseResult(phase="qa", status="passed")},
            review_iteration=2,
            max_review_iterations=5,
        )
        write_delivery_state(tmp_path, state)
        result = read_delivery_state(tmp_path)
        assert result is not None
        assert result.orchestration_mode == "swarm"
        assert result.active_roles == ["risk-officer"]
        assert result.skipped_phases == ["performance"]
        assert result.review_iteration == 2
        assert result.max_review_iterations == 5
        assert "qa" in result.phase_results


class TestWriteDeliveryState:
    def test_creates_delivery_state_json(self, tmp_path):
        from stratus.orchestration.delivery_state import write_delivery_state

        state = DeliveryState(delivery_phase=DeliveryPhase.IMPLEMENTATION, slug="feat")
        write_delivery_state(tmp_path, state)
        assert (tmp_path / "delivery-state.json").exists()

    def test_creates_parent_dirs(self, tmp_path):
        from stratus.orchestration.delivery_state import write_delivery_state

        nested = tmp_path / "sessions" / "abc123"
        state = DeliveryState(delivery_phase=DeliveryPhase.PLANNING, slug="feat")
        write_delivery_state(nested, state)
        assert (nested / "delivery-state.json").exists()

    def test_produces_valid_json(self, tmp_path):
        from stratus.orchestration.delivery_state import write_delivery_state

        state = DeliveryState(delivery_phase=DeliveryPhase.RELEASE, slug="json-test")
        write_delivery_state(tmp_path, state)
        raw = (tmp_path / "delivery-state.json").read_text()
        parsed = json.loads(raw)
        assert parsed["delivery_phase"] == "release"
        assert parsed["slug"] == "json-test"

    def test_roundtrip_write_read(self, tmp_path):
        from stratus.orchestration.delivery_state import (
            read_delivery_state,
            write_delivery_state,
        )

        state = DeliveryState(delivery_phase=DeliveryPhase.PERFORMANCE, slug="roundtrip")
        write_delivery_state(tmp_path, state)
        result = read_delivery_state(tmp_path)
        assert result is not None
        assert result.delivery_phase == DeliveryPhase.PERFORMANCE
        assert result.slug == "roundtrip"


# ---------------------------------------------------------------------------
# get_next_active_phase — phase skipping
# ---------------------------------------------------------------------------


class TestGetNextActivePhase:
    def test_skips_inactive_phase(self):
        from stratus.orchestration.delivery_state import get_next_active_phase

        # IMPLEMENTATION -> QA (active) skipping nothing
        active = {"implementation", "qa", "governance", "release", "learning"}
        result = get_next_active_phase(DeliveryPhase.IMPLEMENTATION, active)
        assert result == DeliveryPhase.QA

    def test_skips_qa_when_not_active(self):
        from stratus.orchestration.delivery_state import get_next_active_phase

        # QA not in active; from IMPLEMENTATION we should jump to GOVERNANCE
        # But IMPLEMENTATION -> QA directly, QA -> GOVERNANCE
        # so we skip QA and find GOVERNANCE through it
        active = {"implementation", "governance", "release", "learning"}
        result = get_next_active_phase(DeliveryPhase.IMPLEMENTATION, active)
        assert result == DeliveryPhase.GOVERNANCE

    def test_returns_none_from_terminal_phase(self):
        from stratus.orchestration.delivery_state import get_next_active_phase

        active = {"learning"}
        result = get_next_active_phase(DeliveryPhase.LEARNING, active)
        assert result is None

    def test_discovery_skips_architecture_to_planning(self):
        from stratus.orchestration.delivery_state import get_next_active_phase

        # ARCHITECTURE not active, should go from DISCOVERY to PLANNING
        active = {
            "discovery",
            "planning",
            "implementation",
            "qa",
            "governance",
            "release",
            "learning",
        }
        result = get_next_active_phase(DeliveryPhase.DISCOVERY, active)
        assert result == DeliveryPhase.PLANNING

    def test_classic_mode_implementation_first_active(self):
        from stratus.orchestration.delivery_state import get_next_active_phase

        # Classic: only implementation, qa, governance, release, learning active
        # From PLANNING -> IMPLEMENTATION
        active = {"implementation", "qa", "governance", "release", "learning"}
        result = get_next_active_phase(DeliveryPhase.PLANNING, active)
        assert result == DeliveryPhase.IMPLEMENTATION
