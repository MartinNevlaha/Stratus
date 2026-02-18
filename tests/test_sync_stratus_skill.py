"""Tests for the /sync-stratus skill file structure."""

from pathlib import Path

import pytest

SKILL_PATHS = [
    Path(__file__).parent.parent / ".claude" / "skills" / "sync-stratus" / "SKILL.md",
    Path(__file__).parent.parent / "plugin" / "skills" / "sync-stratus" / "SKILL.md",
]


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


@pytest.mark.parametrize("path", SKILL_PATHS, ids=["project", "plugin"])
class TestSyncStratusSkill:
    def test_file_exists(self, path: Path) -> None:
        assert path.exists(), f"{path} does not exist"

    def test_has_yaml_frontmatter(self, path: Path) -> None:
        content = path.read_text()
        assert content.startswith("---"), "Missing YAML frontmatter delimiter"
        lines = content.splitlines()
        closing = [i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"]
        assert closing, "Missing closing frontmatter delimiter"

    def test_frontmatter_has_name(self, path: Path) -> None:
        fm = _parse_frontmatter(path.read_text())
        assert fm.get("name") == "sync-stratus"

    def test_frontmatter_has_description(self, path: Path) -> None:
        fm = _parse_frontmatter(path.read_text())
        assert fm.get("description"), "Missing description field"

    def test_frontmatter_has_context_fork(self, path: Path) -> None:
        fm = _parse_frontmatter(path.read_text())
        assert fm.get("context") == "fork"

    def test_frontmatter_no_agent_field(self, path: Path) -> None:
        """sync-stratus should NOT have an agent field — it is a coordinator skill."""
        fm = _parse_frontmatter(path.read_text())
        assert "agent" not in fm

    def test_plan_only_constraint(self, path: Path) -> None:
        content = path.read_text()
        assert "plan" in content.lower() and (
            "do not modify" in content.lower() or "plan-only" in content.lower()
        )

    def test_references_conflict_severity(self, path: Path) -> None:
        content = path.read_text()
        assert "CRITICAL" in content
        assert "MAJOR" in content
        assert "MINOR" in content

    def test_references_agents_skills_rules(self, path: Path) -> None:
        content = path.read_text()
        assert "agents" in content.lower()
        assert "skills" in content.lower()
        assert "rules" in content.lower()

    def test_references_delegation(self, path: Path) -> None:
        content = path.read_text()
        assert "delegation" in content.lower()

    def test_project_and_plugin_identical(self, path: Path) -> None:
        _ = path
        project = SKILL_PATHS[0].read_text()
        plugin = SKILL_PATHS[1].read_text()
        assert project == plugin
