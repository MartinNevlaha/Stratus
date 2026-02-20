"""Tests for delivery models and config (Phase B1-B2)."""

from __future__ import annotations

import json
from dataclasses import fields

import pytest

# ---------------------------------------------------------------------------
# DeliveryPhase
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_delivery_phase_is_str_enum():
    from stratus.orchestration.delivery_models import DeliveryPhase

    assert issubclass(DeliveryPhase, str)


@pytest.mark.unit
def test_delivery_phase_has_9_values():
    from stratus.orchestration.delivery_models import DeliveryPhase

    assert len(DeliveryPhase) == 9


@pytest.mark.unit
def test_delivery_phase_values():
    from stratus.orchestration.delivery_models import DeliveryPhase

    expected = {
        "discovery",
        "architecture",
        "planning",
        "implementation",
        "qa",
        "governance",
        "performance",
        "release",
        "learning",
    }
    assert {p.value for p in DeliveryPhase} == expected


# ---------------------------------------------------------------------------
# OrchestrationMode
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_orchestration_mode_is_str_enum():
    from stratus.orchestration.delivery_models import OrchestrationMode

    assert issubclass(OrchestrationMode, str)


@pytest.mark.unit
def test_orchestration_mode_has_3_values():
    from stratus.orchestration.delivery_models import OrchestrationMode

    assert len(OrchestrationMode) == 3


@pytest.mark.unit
def test_orchestration_mode_values():
    from stratus.orchestration.delivery_models import OrchestrationMode

    assert set(OrchestrationMode) == {
        OrchestrationMode.CLASSIC,
        OrchestrationMode.SWARM,
        OrchestrationMode.AUTO,
    }
    assert OrchestrationMode.CLASSIC == "classic"
    assert OrchestrationMode.SWARM == "swarm"
    assert OrchestrationMode.AUTO == "auto"


# ---------------------------------------------------------------------------
# PhaseResult
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_phase_result_creation_all_fields():
    from stratus.orchestration.delivery_models import PhaseResult

    result = PhaseResult(
        phase="implementation",
        status="passed",
        verdict="PASS",
        details="all tests green",
    )
    assert result.phase == "implementation"
    assert result.status == "passed"
    assert result.verdict == "PASS"
    assert result.details == "all tests green"
    assert result.timestamp  # auto-populated


@pytest.mark.unit
def test_phase_result_defaults():
    from stratus.orchestration.delivery_models import PhaseResult

    result = PhaseResult(phase="qa", status="skipped")
    assert result.verdict is None
    assert result.details == ""
    assert result.timestamp  # auto-populated


# ---------------------------------------------------------------------------
# RoleAssignment
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_role_assignment_creation():
    from stratus.orchestration.delivery_models import RoleAssignment

    role = RoleAssignment(role="qa-engineer", phase="qa", is_lead=True)
    assert role.role == "qa-engineer"
    assert role.phase == "qa"
    assert role.is_lead is True


@pytest.mark.unit
def test_role_assignment_is_lead_default():
    from stratus.orchestration.delivery_models import RoleAssignment

    role = RoleAssignment(role="delivery-implementation-expert", phase="implementation")
    assert role.is_lead is False


# ---------------------------------------------------------------------------
# DeliveryState
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_delivery_state_creation_with_defaults():
    from stratus.orchestration.delivery_models import DeliveryPhase, DeliveryState

    state = DeliveryState(delivery_phase=DeliveryPhase.IMPLEMENTATION, slug="my-feature")
    assert state.delivery_phase == DeliveryPhase.IMPLEMENTATION
    assert state.slug == "my-feature"
    assert state.orchestration_mode == "classic"
    assert state.plan_path is None
    assert state.active_roles == []
    assert state.phase_lead is None
    assert state.skipped_phases == []
    assert state.phase_results == {}
    assert state.review_iteration == 0
    assert state.max_review_iterations == 3
    assert state.rules_snapshot_hash is None
    assert state.last_updated  # auto-populated


@pytest.mark.unit
def test_delivery_state_accepts_delivery_phase_values():
    from stratus.orchestration.delivery_models import DeliveryPhase, DeliveryState

    for phase in DeliveryPhase:
        state = DeliveryState(delivery_phase=phase, slug="test")
        assert state.delivery_phase == phase


@pytest.mark.unit
def test_delivery_state_serialization_roundtrip():
    from stratus.orchestration.delivery_models import (
        DeliveryPhase,
        DeliveryState,
        PhaseResult,
    )

    original = DeliveryState(
        delivery_phase=DeliveryPhase.QA,
        slug="roundtrip-test",
        orchestration_mode="swarm",
        active_roles=["delivery-qa-engineer", "delivery-implementation-expert"],
        phase_lead="delivery-qa-engineer",
        skipped_phases=["performance"],
        phase_results={"implementation": PhaseResult(phase="implementation", status="passed")},
        review_iteration=1,
        max_review_iterations=5,
        rules_snapshot_hash="abc123",
    )

    dumped = original.model_dump()
    restored = DeliveryState.model_validate(dumped)

    assert restored.delivery_phase == original.delivery_phase
    assert restored.slug == original.slug
    assert restored.orchestration_mode == original.orchestration_mode
    assert restored.active_roles == original.active_roles
    assert restored.phase_lead == original.phase_lead
    assert restored.skipped_phases == original.skipped_phases
    assert restored.review_iteration == original.review_iteration
    assert restored.max_review_iterations == original.max_review_iterations
    assert restored.rules_snapshot_hash == original.rules_snapshot_hash
    assert "implementation" in restored.phase_results


@pytest.mark.unit
def test_delivery_state_json_roundtrip():
    from stratus.orchestration.delivery_models import DeliveryPhase, DeliveryState

    state = DeliveryState(delivery_phase=DeliveryPhase.RELEASE, slug="json-test")
    as_json = json.dumps(state.model_dump())
    restored = DeliveryState.model_validate(json.loads(as_json))
    assert restored.delivery_phase == DeliveryPhase.RELEASE
    assert restored.slug == "json-test"


# ---------------------------------------------------------------------------
# DeliveryConfig
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_delivery_config_creation_with_defaults():
    from stratus.orchestration.delivery_config import ALL_PHASES, DeliveryConfig

    config = DeliveryConfig()
    assert config.enabled is True
    assert config.orchestration_mode == "classic"
    assert config.active_phases == ALL_PHASES
    assert config.disabled_invariants == []
    assert config.disabled_agents == []
    assert config.max_review_iterations == 3
    assert config.skip_performance is True


@pytest.mark.unit
def test_delivery_config_is_dataclass():
    from stratus.orchestration.delivery_config import DeliveryConfig

    # Verify it's a proper dataclass by checking fields exist
    field_names = {f.name for f in fields(DeliveryConfig)}
    assert "enabled" in field_names
    assert "orchestration_mode" in field_names
    assert "active_phases" in field_names
    assert "disabled_invariants" in field_names
    assert "disabled_agents" in field_names
    assert "max_review_iterations" in field_names
    assert "skip_performance" in field_names


# ---------------------------------------------------------------------------
# load_delivery_config
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_load_delivery_config_returns_defaults_when_no_file(tmp_path):
    from stratus.orchestration.delivery_config import DeliveryConfig, load_delivery_config

    missing = tmp_path / "nonexistent.json"
    config = load_delivery_config(missing)
    assert isinstance(config, DeliveryConfig)
    assert config.enabled is True
    assert config.orchestration_mode == "classic"


@pytest.mark.unit
def test_load_delivery_config_returns_defaults_when_path_is_none():
    from stratus.orchestration.delivery_config import DeliveryConfig, load_delivery_config

    config = load_delivery_config(None)
    assert isinstance(config, DeliveryConfig)
    assert config.enabled is True


@pytest.mark.unit
def test_load_delivery_config_loads_from_file(tmp_path):
    from stratus.orchestration.delivery_config import load_delivery_config

    config_file = tmp_path / ".ai-framework.json"
    config_file.write_text(
        json.dumps(
            {
                "delivery_framework": {
                    "enabled": True,
                    "orchestration_mode": "swarm",
                    "active_phases": ["implementation", "qa"],
                    "disabled_invariants": ["no-direct-commits"],
                    "disabled_agents": ["governance-reviewer"],
                    "max_review_iterations": 5,
                    "skip_performance": False,
                }
            }
        )
    )

    config = load_delivery_config(config_file)
    assert config.enabled is True
    assert config.orchestration_mode == "swarm"
    assert config.active_phases == ["implementation", "qa"]
    assert config.disabled_invariants == ["no-direct-commits"]
    assert config.disabled_agents == ["governance-reviewer"]
    assert config.max_review_iterations == 5
    assert config.skip_performance is False


@pytest.mark.unit
def test_load_delivery_config_ignores_invalid_json(tmp_path):
    from stratus.orchestration.delivery_config import load_delivery_config

    bad_file = tmp_path / ".ai-framework.json"
    bad_file.write_text("{ not valid json }")

    config = load_delivery_config(bad_file)
    # Should fall back to defaults silently
    assert config.enabled is True


@pytest.mark.unit
def test_load_delivery_config_env_override_orchestration_mode(tmp_path, monkeypatch):
    from stratus.orchestration.delivery_config import load_delivery_config

    monkeypatch.setenv("AI_FRAMEWORK_ORCHESTRATION_MODE", "swarm")
    config = load_delivery_config(None)
    assert config.orchestration_mode == "swarm"


@pytest.mark.unit
def test_load_delivery_config_env_override_orchestration_mode_invalid(tmp_path, monkeypatch):
    from stratus.orchestration.delivery_config import load_delivery_config

    monkeypatch.setenv("AI_FRAMEWORK_ORCHESTRATION_MODE", "not-a-mode")
    config = load_delivery_config(None)
    # Invalid values silently ignored; default preserved
    assert config.orchestration_mode == "classic"


@pytest.mark.unit
def test_load_delivery_config_env_override_enabled_true(monkeypatch):
    from stratus.orchestration.delivery_config import load_delivery_config

    monkeypatch.setenv("AI_FRAMEWORK_DELIVERY_ENABLED", "true")
    config = load_delivery_config(None)
    assert config.enabled is True


@pytest.mark.unit
def test_load_delivery_config_env_override_enabled_false(monkeypatch):
    from stratus.orchestration.delivery_config import load_delivery_config

    monkeypatch.setenv("AI_FRAMEWORK_DELIVERY_ENABLED", "false")
    config = load_delivery_config(None)
    assert config.enabled is False


@pytest.mark.unit
def test_load_delivery_config_env_override_enabled_one(monkeypatch):
    from stratus.orchestration.delivery_config import load_delivery_config

    monkeypatch.setenv("AI_FRAMEWORK_DELIVERY_ENABLED", "1")
    config = load_delivery_config(None)
    assert config.enabled is True


@pytest.mark.unit
def test_load_delivery_config_env_overrides_file(tmp_path, monkeypatch):
    """Env var takes precedence over file config."""
    from stratus.orchestration.delivery_config import load_delivery_config

    config_file = tmp_path / ".ai-framework.json"
    config_file.write_text(json.dumps({"delivery_framework": {"orchestration_mode": "classic"}}))
    monkeypatch.setenv("AI_FRAMEWORK_ORCHESTRATION_MODE", "swarm")

    config = load_delivery_config(config_file)
    assert config.orchestration_mode == "swarm"


# ---------------------------------------------------------------------------
# DEFAULT_ACTIVE_PHASES and get_default_phases
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_default_active_phases_classic_has_5_phases():
    from stratus.orchestration.delivery_models import (
        DEFAULT_ACTIVE_PHASES,
        OrchestrationMode,
    )

    classic_phases = DEFAULT_ACTIVE_PHASES[OrchestrationMode.CLASSIC]
    assert len(classic_phases) == 5


@pytest.mark.unit
def test_default_active_phases_swarm_has_9_phases():
    from stratus.orchestration.delivery_models import (
        DEFAULT_ACTIVE_PHASES,
        DeliveryPhase,
        OrchestrationMode,
    )

    swarm_phases = DEFAULT_ACTIVE_PHASES[OrchestrationMode.SWARM]
    assert len(swarm_phases) == 9
    assert set(swarm_phases) == set(DeliveryPhase)


@pytest.mark.unit
def test_get_default_phases_classic():
    from stratus.orchestration.delivery_models import (
        DeliveryPhase,
        OrchestrationMode,
        get_default_phases,
    )

    phases = get_default_phases(OrchestrationMode.CLASSIC)
    assert DeliveryPhase.IMPLEMENTATION in phases
    assert DeliveryPhase.QA in phases
    assert DeliveryPhase.GOVERNANCE in phases
    assert DeliveryPhase.RELEASE in phases
    assert DeliveryPhase.LEARNING in phases
    assert len(phases) == 5


@pytest.mark.unit
def test_get_default_phases_swarm():
    from stratus.orchestration.delivery_models import (
        DeliveryPhase,
        OrchestrationMode,
        get_default_phases,
    )

    phases = get_default_phases(OrchestrationMode.SWARM)
    assert len(phases) == 9
    assert set(phases) == set(DeliveryPhase)


@pytest.mark.unit
def test_get_default_phases_auto():
    from stratus.orchestration.delivery_models import (
        OrchestrationMode,
        get_default_phases,
    )

    phases = get_default_phases(OrchestrationMode.AUTO)
    assert len(phases) == 5


@pytest.mark.unit
def test_get_default_phases_accepts_string():
    from stratus.orchestration.delivery_models import (
        OrchestrationMode,
        get_default_phases,
    )

    phases = get_default_phases("classic")
    classic_phases = get_default_phases(OrchestrationMode.CLASSIC)
    assert phases == classic_phases


@pytest.mark.unit
def test_get_default_phases_returns_new_list():
    """Mutation of returned list must not affect DEFAULT_ACTIVE_PHASES."""
    from stratus.orchestration.delivery_models import (
        OrchestrationMode,
        get_default_phases,
    )

    phases1 = get_default_phases(OrchestrationMode.CLASSIC)
    phases1.clear()
    phases2 = get_default_phases(OrchestrationMode.CLASSIC)
    assert len(phases2) == 5
