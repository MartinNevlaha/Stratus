"""Tests for runtime_agents catalog and filtering."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from stratus.bootstrap.models import ServiceType

# ---------------------------------------------------------------------------
# AgentSpec dataclass
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_agent_spec_fields():
    from stratus.runtime_agents import AgentSpec

    spec = AgentSpec(
        filename="delivery-backend-engineer.md",
        applicable_stacks=frozenset({ServiceType.NESTJS}),
        layer="engineering",
        optional=False,
    )
    assert spec.filename == "delivery-backend-engineer.md"
    assert spec.applicable_stacks == frozenset({ServiceType.NESTJS})
    assert spec.layer == "engineering"
    assert spec.optional is False


@pytest.mark.unit
def test_agent_spec_optional_default_false():
    from stratus.runtime_agents import AgentSpec

    spec = AgentSpec(
        filename="delivery-tpm.md",
        applicable_stacks=None,
        layer="process",
    )
    assert spec.optional is False


@pytest.mark.unit
def test_agent_spec_is_frozen():
    from stratus.runtime_agents import AgentSpec

    spec = AgentSpec(filename="x.md", applicable_stacks=None, layer="process")
    with pytest.raises((AttributeError, TypeError)):
        spec.filename = "y.md"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SkillSpec dataclass
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_skill_spec_fields():
    from stratus.runtime_agents import SkillSpec

    spec = SkillSpec(
        dirname="run-discovery",
        agent_filename="delivery-product-owner.md",
        phase="discovery",
        optional=True,
    )
    assert spec.dirname == "run-discovery"
    assert spec.agent_filename == "delivery-product-owner.md"
    assert spec.phase == "discovery"
    assert spec.optional is True


@pytest.mark.unit
def test_skill_spec_optional_default_false():
    from stratus.runtime_agents import SkillSpec

    spec = SkillSpec(
        dirname="plan-sprint",
        agent_filename="delivery-tpm.md",
        phase="planning",
    )
    assert spec.optional is False


@pytest.mark.unit
def test_skill_spec_is_frozen():
    from stratus.runtime_agents import SkillSpec

    spec = SkillSpec(dirname="x", agent_filename="y.md", phase="planning")
    with pytest.raises((AttributeError, TypeError)):
        spec.dirname = "z"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# AGENT_CATALOG size
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_agent_catalog_has_19_entries():
    from stratus.runtime_agents import AGENT_CATALOG

    assert len(AGENT_CATALOG) == 19


# ---------------------------------------------------------------------------
# SKILL_CATALOG size
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_skill_catalog_has_7_entries():
    from stratus.runtime_agents import SKILL_CATALOG

    assert len(SKILL_CATALOG) == 7


# ---------------------------------------------------------------------------
# filter_agents — universal (no stacks)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_filter_agents_no_stacks_returns_universal_non_optional():
    from stratus.runtime_agents import filter_agents

    result = filter_agents(set())
    filenames = {s.filename for s in result}

    # Should include universal non-optional agents
    assert "delivery-tpm.md" in filenames
    assert "delivery-risk-officer.md" in filenames
    assert "delivery-devops-engineer.md" in filenames

    # Should exclude optional agents (not enabled)
    assert "delivery-product-owner.md" not in filenames
    assert "delivery-strategic-architect.md" not in filenames

    # Should exclude stack-specific agents
    assert "delivery-backend-engineer.md" not in filenames
    assert "delivery-frontend-engineer.md" not in filenames

    # Verify all returned are universal (applicable_stacks is None) and non-optional
    for spec in result:
        assert spec.applicable_stacks is None, f"{spec.filename} should be universal"
        assert spec.optional is False, f"{spec.filename} should not be optional"


# ---------------------------------------------------------------------------
# filter_agents — with NESTJS
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_filter_agents_nestjs_includes_backend_engineer():
    from stratus.runtime_agents import filter_agents

    result = filter_agents({ServiceType.NESTJS})
    filenames = {s.filename for s in result}

    assert "delivery-backend-engineer.md" in filenames
    # Universal non-optional agents also included
    assert "delivery-tpm.md" in filenames
    # Frontend should be excluded
    assert "delivery-frontend-engineer.md" not in filenames
    # Mobile should be excluded
    assert "delivery-mobile-engineer.md" not in filenames


@pytest.mark.unit
def test_filter_agents_python_includes_backend_engineer():
    from stratus.runtime_agents import filter_agents

    result = filter_agents({ServiceType.PYTHON})
    filenames = {s.filename for s in result}

    assert "delivery-backend-engineer.md" in filenames
    assert "delivery-frontend-engineer.md" not in filenames


# ---------------------------------------------------------------------------
# filter_agents — with NEXTJS
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_filter_agents_nextjs_includes_frontend_engineer():
    from stratus.runtime_agents import filter_agents

    result = filter_agents({ServiceType.NEXTJS})
    filenames = {s.filename for s in result}

    assert "delivery-frontend-engineer.md" in filenames
    assert "delivery-backend-engineer.md" not in filenames
    assert "delivery-mobile-engineer.md" not in filenames


# ---------------------------------------------------------------------------
# filter_agents — with REACT_NATIVE
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_filter_agents_react_native_includes_frontend_and_mobile():
    from stratus.runtime_agents import filter_agents

    result = filter_agents({ServiceType.REACT_NATIVE})
    filenames = {s.filename for s in result}

    assert "delivery-frontend-engineer.md" in filenames
    assert "delivery-mobile-engineer.md" in filenames
    # Backend should be excluded
    assert "delivery-backend-engineer.md" not in filenames


# ---------------------------------------------------------------------------
# filter_agents — optional phase handling
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_filter_agents_optional_excluded_by_default():
    from stratus.runtime_agents import filter_agents

    result = filter_agents(set())
    filenames = {s.filename for s in result}

    assert "delivery-product-owner.md" not in filenames
    assert "delivery-strategic-architect.md" not in filenames
    assert "delivery-system-architect.md" not in filenames
    assert "delivery-performance-engineer.md" not in filenames


@pytest.mark.unit
def test_filter_agents_optional_included_when_phase_enabled():
    from stratus.runtime_agents import filter_agents

    result = filter_agents(set(), enabled_phases={"discovery"})
    filenames = {s.filename for s in result}

    assert "delivery-product-owner.md" in filenames
    # strategic-architect also has "discovery" in its phases
    assert "delivery-strategic-architect.md" in filenames
    # Agents gated on other phases still excluded
    assert "delivery-performance-engineer.md" not in filenames


@pytest.mark.unit
def test_filter_agents_optional_architecture_phase():
    from stratus.runtime_agents import filter_agents

    result = filter_agents(set(), enabled_phases={"architecture"})
    filenames = {s.filename for s in result}

    assert "delivery-strategic-architect.md" in filenames
    assert "delivery-system-architect.md" in filenames
    assert "delivery-product-owner.md" not in filenames


@pytest.mark.unit
def test_filter_agents_optional_performance_phase():
    from stratus.runtime_agents import filter_agents

    result = filter_agents(set(), enabled_phases={"performance"})
    filenames = {s.filename for s in result}

    assert "delivery-performance-engineer.md" in filenames


# ---------------------------------------------------------------------------
# filter_skills
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_filter_skills_no_config_returns_non_optional():
    from stratus.runtime_agents import filter_skills

    result = filter_skills()
    dirnames = {s.dirname for s in result}

    # Non-optional skills should be included
    assert "plan-sprint" in dirnames
    assert "security-review" in dirnames
    assert "release-prepare" in dirnames
    assert "governance-audit" in dirnames

    # Optional skills should be excluded
    assert "run-discovery" not in dirnames
    assert "create-architecture" not in dirnames
    assert "performance-benchmark" not in dirnames


@pytest.mark.unit
def test_filter_skills_with_enabled_phases_includes_optional():
    from stratus.runtime_agents import filter_skills

    result = filter_skills(enabled_phases={"discovery"})
    dirnames = {s.dirname for s in result}

    assert "run-discovery" in dirnames
    # Other optional phases still excluded
    assert "create-architecture" not in dirnames
    assert "performance-benchmark" not in dirnames


@pytest.mark.unit
def test_filter_skills_with_multiple_phases():
    from stratus.runtime_agents import filter_skills

    result = filter_skills(enabled_phases={"discovery", "architecture", "performance"})
    dirnames = {s.dirname for s in result}

    assert "run-discovery" in dirnames
    assert "create-architecture" in dirnames
    assert "performance-benchmark" in dirnames
    # Non-optional always included
    assert "plan-sprint" in dirnames


@pytest.mark.unit
def test_filter_skills_empty_phases_set_excludes_optional():
    from stratus.runtime_agents import filter_skills

    result = filter_skills(enabled_phases=set())
    dirnames = {s.dirname for s in result}

    assert "run-discovery" not in dirnames
    assert "plan-sprint" in dirnames


# ---------------------------------------------------------------------------
# read_agent_template
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_read_agent_template_success():
    from stratus.runtime_agents import read_agent_template

    mock_resource = MagicMock()
    mock_resource.read_text.return_value = "# Delivery TPM\n\nAgent content here."

    mock_pkg = MagicMock()
    mock_pkg.joinpath.return_value = mock_resource

    with patch("stratus.runtime_agents._catalog.resources.files", return_value=mock_pkg):
        content = read_agent_template("delivery-tpm.md")

    assert content == "# Delivery TPM\n\nAgent content here."
    mock_pkg.joinpath.assert_called_once_with("delivery-tpm.md")
    mock_resource.read_text.assert_called_once_with(encoding="utf-8")


@pytest.mark.unit
def test_read_agent_template_missing_raises_file_not_found():
    from stratus.runtime_agents import read_agent_template

    mock_resource = MagicMock()
    mock_resource.read_text.side_effect = FileNotFoundError("no such file")

    mock_pkg = MagicMock()
    mock_pkg.joinpath.return_value = mock_resource

    with patch("stratus.runtime_agents._catalog.resources.files", return_value=mock_pkg):
        with pytest.raises(FileNotFoundError):
            read_agent_template("nonexistent.md")


# ---------------------------------------------------------------------------
# get_detected_types
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_detected_types_empty_graph():
    from stratus.runtime_agents import get_detected_types

    assert get_detected_types(None) == set()
    assert get_detected_types({}) == set()


@pytest.mark.unit
def test_get_detected_types_no_services():
    from stratus.runtime_agents import get_detected_types

    graph = {"services": []}
    assert get_detected_types(graph) == set()


@pytest.mark.unit
def test_get_detected_types_single_service():
    from stratus.runtime_agents import get_detected_types

    graph = {
        "services": [{"name": "api", "type": "nestjs", "path": "/api", "language": "typescript"}]
    }
    result = get_detected_types(graph)
    assert result == {ServiceType.NESTJS}


@pytest.mark.unit
def test_get_detected_types_multiple_services():
    from stratus.runtime_agents import get_detected_types

    graph = {
        "services": [
            {"name": "api", "type": "nestjs", "path": "/api", "language": "typescript"},
            {"name": "web", "type": "nextjs", "path": "/web", "language": "typescript"},
            {"name": "app", "type": "react_native", "path": "/app", "language": "typescript"},
        ]
    }
    result = get_detected_types(graph)
    assert result == {ServiceType.NESTJS, ServiceType.NEXTJS, ServiceType.REACT_NATIVE}


@pytest.mark.unit
def test_get_detected_types_skips_unknown_type():
    from stratus.runtime_agents import get_detected_types

    graph = {
        "services": [
            {"name": "api", "type": "nestjs", "path": "/api", "language": "typescript"},
            {"name": "weird", "type": "totally-invalid", "path": "/x", "language": "x"},
        ]
    }
    result = get_detected_types(graph)
    assert result == {ServiceType.NESTJS}


@pytest.mark.unit
def test_get_detected_types_missing_type_field():
    from stratus.runtime_agents import get_detected_types

    graph = {
        "services": [
            {"name": "api", "path": "/api", "language": "typescript"},  # no "type"
        ]
    }
    result = get_detected_types(graph)
    assert result == set()


# ---------------------------------------------------------------------------
# Public API exports from __init__
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_public_api_exports():
    import stratus.runtime_agents as ra

    assert hasattr(ra, "AgentSpec")
    assert hasattr(ra, "SkillSpec")
    assert hasattr(ra, "AGENT_CATALOG")
    assert hasattr(ra, "SKILL_CATALOG")
    assert hasattr(ra, "filter_agents")
    assert hasattr(ra, "filter_skills")
    assert hasattr(ra, "read_agent_template")
    assert hasattr(ra, "read_skill_template")
    assert hasattr(ra, "get_detected_types")
