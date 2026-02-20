"""Tests for the /spec skill file structure."""

from pathlib import Path

import pytest

SKILL_PATH = (
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


@pytest.mark.unit
class TestSpecSkill:
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
        assert fm.get("name") == "spec"

    def test_frontmatter_has_context_fork(self) -> None:
        fm = _parse_frontmatter(SKILL_PATH.read_text())
        assert fm.get("context") == "fork"

    def test_frontmatter_no_agent_field(self) -> None:
        """Spec skill should NOT have an agent field — it's a coordinator."""
        fm = _parse_frontmatter(SKILL_PATH.read_text())
        assert "agent" not in fm

    def test_references_task_tool(self) -> None:
        content = SKILL_PATH.read_text()
        assert "Task tool" in content

    def test_references_delegation(self) -> None:
        content = SKILL_PATH.read_text()
        assert "delegate" in content.lower()

    def test_references_spec_complex(self) -> None:
        content = SKILL_PATH.read_text()
        assert "spec-complex" in content

    def test_has_four_phases(self) -> None:
        content = SKILL_PATH.read_text()
        phases = [
            line
            for line in content.splitlines()
            if line.startswith("## Phase") and "Context" not in line
        ]
        assert len(phases) == 4
