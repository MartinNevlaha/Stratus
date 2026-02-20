"""Tests for team composition and mode validation."""

from __future__ import annotations

import pytest

from stratus.registry.validation import (
    validate_mode_agents,
    validate_team_composition,
    validate_write_permissions,
)


@pytest.mark.unit
def test_validate_team_all_exist():
    # Both framework-expert and spec-reviewer-compliance have verify/implement phases.
    # Use agents that both exist in the same phase.
    # spec-reviewer-compliance and spec-reviewer-quality are both in "verify".
    warnings = validate_team_composition(
        ["spec-reviewer-compliance", "spec-reviewer-quality"], phase="verify"
    )
    assert warnings == []


@pytest.mark.unit
def test_validate_team_unknown_agent():
    warnings = validate_team_composition(["ghost-agent"], phase="implement")
    assert len(warnings) == 1
    assert "ghost-agent" in warnings[0].message
    assert "not found" in warnings[0].message


@pytest.mark.unit
def test_validate_team_wrong_phase():
    # framework-expert is in phases=["implement"], not "plan"
    warnings = validate_team_composition(["framework-expert"], phase="plan")
    assert len(warnings) == 1
    assert "framework-expert" in warnings[0].message
    assert "plan" in warnings[0].message


@pytest.mark.unit
def test_validate_mode_default_has_agents():
    warnings = validate_mode_agents("default")
    assert warnings == []


@pytest.mark.unit
def test_validate_mode_sworm_has_no_agents():
    warnings = validate_mode_agents("sworm")
    assert len(warnings) == 1
    assert "sworm" in warnings[0].message


@pytest.mark.unit
def test_validate_mode_unknown_warns():
    warnings = validate_mode_agents("unknown-mode-xyz")
    assert len(warnings) == 1
    assert "unknown-mode-xyz" in warnings[0].message


@pytest.mark.unit
def test_validate_write_in_verify():
    # qa-engineer has can_write=True and is assigned to verify
    warnings = validate_write_permissions(["qa-engineer"], phase="verify")
    assert len(warnings) == 1
    assert "qa-engineer" in warnings[0].message
    assert "verify" in warnings[0].message


@pytest.mark.unit
def test_validate_write_in_implement():
    # implement is not a review phase -> no warnings regardless of can_write
    warnings = validate_write_permissions(["framework-expert"], phase="implement")
    assert warnings == []


@pytest.mark.unit
def test_validate_write_nonexistent_agent_ignored():
    # Unknown agents should not crash; skip them silently
    warnings = validate_write_permissions(["nonexistent-agent"], phase="verify")
    assert warnings == []
