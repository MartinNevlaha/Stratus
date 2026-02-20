"""Tests for the /spec-complex skill file structure."""

from pathlib import Path

import pytest

SKILL_PATH = (
    Path(__file__).parent.parent
    / "src"
    / "stratus"
    / "runtime_agents"
    / "skills"
    / "spec-complex"
    / "SKILL.md"
)
SPEC_SKILL_PATH = (
    Path(__file__).parent.parent
    / "src"
    / "stratus"
    / "runtime_agents"
    / "skills"
    / "spec"
    / "SKILL.md"
)


def _parse_frontmatter(content: str) -> dict[str, str]:
    """Parse YAML frontmatter from skill file."""
    lines = content.strip().splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fm: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip().strip('"')
    return fm


def _extract_phase_headings(content: str) -> list[str]:
    """Extract phase headings from skill content."""
    phases = []
    for line in content.splitlines():
        if line.startswith("## Phase") and "Context" not in line:
            phase_name = line.replace("##", "").strip()
            phases.append(phase_name)
    return phases


@pytest.mark.unit
class TestSpecComplexSkill:
    def test_file_exists(self) -> None:
        assert SKILL_PATH.exists(), f"{SKILL_PATH} does not exist"

    def test_has_yaml_frontmatter(self) -> None:
        content = SKILL_PATH.read_text()
        assert content.startswith("---"), "Missing YAML frontmatter delimiter"
        lines = content.splitlines()
        closing = [i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"]
        assert closing, "Missing closing frontmatter delimiter"

    def test_frontmatter_has_name(self) -> None:
        fm = _parse_frontmatter(SKILL_PATH.read_text())
        assert fm.get("name") == "spec-complex"

    def test_frontmatter_has_description(self) -> None:
        fm = _parse_frontmatter(SKILL_PATH.read_text())
        assert "description" in fm
        assert "8-phase" in fm["description"]

    def test_frontmatter_has_context_fork(self) -> None:
        fm = _parse_frontmatter(SKILL_PATH.read_text())
        assert fm.get("context") == "fork"

    def test_frontmatter_no_agent_field(self) -> None:
        fm = _parse_frontmatter(SKILL_PATH.read_text())
        assert "agent" not in fm

    def test_has_eight_phases(self) -> None:
        phases = _extract_phase_headings(SKILL_PATH.read_text())
        assert len(phases) == 8, f"Expected 8 phases, found {len(phases)}: {phases}"

    def test_phase_1_is_discovery(self) -> None:
        phases = _extract_phase_headings(SKILL_PATH.read_text())
        assert len(phases) >= 1
        assert "Discovery" in phases[0]

    def test_phase_2_is_design(self) -> None:
        phases = _extract_phase_headings(SKILL_PATH.read_text())
        assert len(phases) >= 2
        assert "Design" in phases[1]

    def test_phase_3_is_governance(self) -> None:
        phases = _extract_phase_headings(SKILL_PATH.read_text())
        assert len(phases) >= 3
        assert "Governance" in phases[2]

    def test_phase_4_is_plan(self) -> None:
        phases = _extract_phase_headings(SKILL_PATH.read_text())
        assert len(phases) >= 4
        assert "Plan" in phases[3]

    def test_phase_5_is_accept(self) -> None:
        phases = _extract_phase_headings(SKILL_PATH.read_text())
        assert len(phases) >= 5
        assert "Accept" in phases[4]

    def test_phase_6_is_implement(self) -> None:
        phases = _extract_phase_headings(SKILL_PATH.read_text())
        assert len(phases) >= 6
        assert "Implement" in phases[5]

    def test_phase_7_is_review(self) -> None:
        phases = _extract_phase_headings(SKILL_PATH.read_text())
        assert len(phases) >= 7
        assert "Review" in phases[6]

    def test_phase_8_is_learn(self) -> None:
        phases = _extract_phase_headings(SKILL_PATH.read_text())
        assert len(phases) >= 8
        assert "Learn" in phases[7]

    def test_references_task_tool(self) -> None:
        content = SKILL_PATH.read_text()
        assert "Task tool" in content

    def test_references_delegation(self) -> None:
        content = SKILL_PATH.read_text()
        assert "delegate" in content.lower()

    def test_has_when_to_use_section(self) -> None:
        content = SKILL_PATH.read_text()
        assert "When to Use" in content

    def test_mentions_security_sensitive(self) -> None:
        content = SKILL_PATH.read_text()
        assert "security" in content.lower()

    def test_mentions_api_contracts(self) -> None:
        content = SKILL_PATH.read_text()
        assert "API" in content

    def test_has_governance_skip_condition(self) -> None:
        content = SKILL_PATH.read_text()
        assert "Skip condition" in content or "skip" in content.lower()

    def test_has_user_approval_at_accept_phase(self) -> None:
        content = SKILL_PATH.read_text()
        assert "Phase 5: Accept" in content
        assert "approval" in content.lower() or "approve" in content.lower()

    def test_has_fix_loop_handling(self) -> None:
        content = SKILL_PATH.read_text()
        assert "fix loop" in content.lower() or "fix-loop" in content.lower()

    def test_no_write_on_production_files(self) -> None:
        content = SKILL_PATH.read_text()
        assert "NEVER" in content
        assert "Write" in content or "Edit" in content


@pytest.mark.unit
class TestSpecComplexVsSpec:
    def test_spec_complex_has_more_phases_than_spec(self) -> None:
        spec_phases = _extract_phase_headings(SPEC_SKILL_PATH.read_text())
        complex_phases = _extract_phase_headings(SKILL_PATH.read_text())
        assert len(complex_phases) > len(spec_phases)

    def test_different_skill_names(self) -> None:
        spec_fm = _parse_frontmatter(SPEC_SKILL_PATH.read_text())
        complex_fm = _parse_frontmatter(SKILL_PATH.read_text())
        assert spec_fm.get("name") != complex_fm.get("name")


@pytest.mark.unit
class TestSpecComplexCatalog:
    def test_spec_complex_in_core_skill_dirnames(self) -> None:
        from stratus.runtime_agents import CORE_SKILL_DIRNAMES

        assert "spec-complex" in CORE_SKILL_DIRNAMES

    def test_spec_complex_after_spec_in_catalog(self) -> None:
        from stratus.runtime_agents import CORE_SKILL_DIRNAMES

        spec_idx = CORE_SKILL_DIRNAMES.index("spec")
        complex_idx = CORE_SKILL_DIRNAMES.index("spec-complex")
        assert complex_idx > spec_idx
