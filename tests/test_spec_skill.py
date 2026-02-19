"""Tests for the /spec skill file structure."""

from pathlib import Path

import pytest

SKILL_PATHS = [
    Path(__file__).parent.parent / ".claude" / "skills" / "spec" / "SKILL.md",
    Path(__file__).parent.parent / "plugin" / "skills" / "spec" / "SKILL.md",
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
class TestSpecSkill:
    def test_file_exists(self, path: Path) -> None:
        assert path.exists(), f"{path} does not exist"

    def test_has_yaml_frontmatter(self, path: Path) -> None:
        content = path.read_text()
        assert content.startswith("---"), "Missing YAML frontmatter delimiter"
        # Find closing delimiter
        lines = content.splitlines()
        closing = [i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"]
        assert closing, "Missing closing frontmatter delimiter"

    def test_frontmatter_has_name(self, path: Path) -> None:
        fm = _parse_frontmatter(path.read_text())
        assert fm.get("name") == "spec"

    def test_frontmatter_has_context_fork(self, path: Path) -> None:
        fm = _parse_frontmatter(path.read_text())
        assert fm.get("context") == "fork"

    def test_frontmatter_no_agent_field(self, path: Path) -> None:
        """Spec skill should NOT have an agent field — it's a coordinator."""
        fm = _parse_frontmatter(path.read_text())
        assert "agent" not in fm

    def test_references_task_tool(self, path: Path) -> None:
        content = path.read_text()
        assert "Task tool" in content or "Task" in content

    def test_references_delegation(self, path: Path) -> None:
        content = path.read_text()
        assert "delegate" in content.lower()

    def test_references_both_modes(self, path: Path) -> None:
        content = path.read_text()
        assert "Default" in content
        assert "Swords" in content

    def test_project_and_plugin_identical(self, path: Path) -> None:
        _ = path  # parametrized but we compare both
        project = SKILL_PATHS[0].read_text()
        plugin = SKILL_PATHS[1].read_text()
        # Plugin generalizes agent names: framework-expert → implementation-expert
        normalized = project.replace("framework-expert", "implementation-expert")
        assert normalized == plugin
