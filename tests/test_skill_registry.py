"""Tests for skills/registry.py — SkillRegistry discovery, lookup, validation."""

from __future__ import annotations

from pathlib import Path

from stratus.skills.registry import SkillRegistry

_MIN = {"name": "run-tests", "description": "Tests", "agent": "qa"}


def _write_skill(
    skills_dir: Path,
    slug: str,
    frontmatter: dict[str, str],
    body: str = "Do the thing.",
) -> Path:
    """Helper: create a SKILL.md in skills_dir/<slug>/SKILL.md."""
    skill_dir = skills_dir / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    lines = ["---"]
    for k, v in frontmatter.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    lines.append(body)
    (skill_dir / "SKILL.md").write_text("\n".join(lines))
    return skill_dir / "SKILL.md"


class TestSkillRegistryInit:
    def test_accepts_skills_dir(self, tmp_path):
        reg = SkillRegistry(skills_dir=tmp_path)
        assert reg is not None

    def test_accepts_optional_agents_dir(self, tmp_path):
        agents = tmp_path / "agents"
        agents.mkdir()
        reg = SkillRegistry(skills_dir=tmp_path, agents_dir=agents)
        assert reg is not None

    def test_agents_dir_defaults_to_none(self, tmp_path):
        reg = SkillRegistry(skills_dir=tmp_path)
        assert reg._agents_dir is None


class TestSkillRegistryDiscover:
    def test_discover_finds_skill_md_files(self, tmp_path):
        fm = {"name": "run-tests", "description": "Runs tests", "agent": "qa-engineer"}
        _write_skill(tmp_path, "run-tests", fm)
        reg = SkillRegistry(skills_dir=tmp_path)
        skills = reg.discover()
        assert len(skills) == 1
        assert skills[0].name == "run-tests"

    def test_discover_multiple_skills(self, tmp_path):
        _write_skill(tmp_path, "run-tests", _MIN)
        _write_skill(
            tmp_path,
            "explain",
            {"name": "explain", "description": "Explain", "agent": "arch"},
        )
        reg = SkillRegistry(skills_dir=tmp_path)
        skills = reg.discover()
        assert len(skills) == 2

    def test_discover_parses_frontmatter_correctly(self, tmp_path):
        fm = {
            "name": "my-skill",
            "description": "Does something useful",
            "agent": "framework-expert",
            "context": "inline",
            "priority": "3",
            "tags": "python, testing",
            "triggers": "run my skill, do the thing",
        }
        _write_skill(tmp_path, "my-skill", fm)
        reg = SkillRegistry(skills_dir=tmp_path)
        skills = reg.discover()
        assert len(skills) == 1
        s = skills[0]
        assert s.name == "my-skill"
        assert s.description == "Does something useful"
        assert s.agent == "framework-expert"
        assert s.context == "inline"
        assert s.priority == 3
        assert s.tags == ["python", "testing"]
        assert s.triggers == ["run my skill", "do the thing"]

    def test_discover_missing_frontmatter_skips_file(self, tmp_path):
        skill_dir = tmp_path / "bad-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("No frontmatter here, just plain text.")
        reg = SkillRegistry(skills_dir=tmp_path)
        skills = reg.discover()
        assert len(skills) == 0

    def test_discover_missing_required_fields_skips_file(self, tmp_path):
        # Missing 'agent' field
        skill_dir = tmp_path / "incomplete"
        skill_dir.mkdir()
        text = "---\nname: incomplete\ndescription: Missing agent\n---\n"
        (skill_dir / "SKILL.md").write_text(text)
        reg = SkillRegistry(skills_dir=tmp_path)
        skills = reg.discover()
        assert len(skills) == 0

    def test_discover_sets_source_local(self, tmp_path):
        _write_skill(tmp_path, "run-tests", _MIN)
        reg = SkillRegistry(skills_dir=tmp_path)
        skills = reg.discover()
        assert skills[0].source == "local"

    def test_discover_sets_body(self, tmp_path):
        _write_skill(tmp_path, "run-tests", _MIN, body="Run the test suite.")
        reg = SkillRegistry(skills_dir=tmp_path)
        skills = reg.discover()
        assert "Run the test suite." in skills[0].body

    def test_discover_sets_path(self, tmp_path):
        _write_skill(tmp_path, "run-tests", _MIN)
        reg = SkillRegistry(skills_dir=tmp_path)
        skills = reg.discover()
        assert "SKILL.md" in skills[0].path

    def test_discover_sets_content_hash(self, tmp_path):
        _write_skill(tmp_path, "run-tests", _MIN)
        reg = SkillRegistry(skills_dir=tmp_path)
        skills = reg.discover()
        assert len(skills[0].content_hash) == 64  # sha256 hex

    def test_discover_empty_dir_returns_empty(self, tmp_path):
        reg = SkillRegistry(skills_dir=tmp_path)
        skills = reg.discover()
        assert skills == []

    def test_discover_nonexistent_dir_returns_empty(self, tmp_path):
        reg = SkillRegistry(skills_dir=tmp_path / "nonexistent")
        skills = reg.discover()
        assert skills == []

    def test_discover_ignores_files_not_in_subdirs(self, tmp_path):
        # SKILL.md directly in skills_dir (not in a subdir) should be ignored
        content = "---\nname: x\ndescription: d\nagent: a\n---\n"
        (tmp_path / "SKILL.md").write_text(content)
        reg = SkillRegistry(skills_dir=tmp_path)
        skills = reg.discover()
        assert len(skills) == 0


class TestSkillRegistryGet:
    def test_get_returns_manifest_by_name(self, tmp_path):
        _write_skill(tmp_path, "run-tests", _MIN)
        reg = SkillRegistry(skills_dir=tmp_path)
        reg.discover()
        skill = reg.get("run-tests")
        assert skill is not None
        assert skill.name == "run-tests"

    def test_get_returns_none_for_unknown(self, tmp_path):
        reg = SkillRegistry(skills_dir=tmp_path)
        reg.discover()
        assert reg.get("nonexistent") is None

    def test_get_before_discover_returns_none(self, tmp_path):
        _write_skill(tmp_path, "run-tests", _MIN)
        reg = SkillRegistry(skills_dir=tmp_path)
        assert reg.get("run-tests") is None


class TestSkillRegistryFilterByPhase:
    def test_filter_by_phase_returns_matching_skills(self, tmp_path):
        fm_verify = {
            "name": "verify-skill",
            "description": "Verify phase skill",
            "agent": "qa",
            "requires_phase": "verify",
        }
        _write_skill(tmp_path, "verify-skill", fm_verify)
        _write_skill(
            tmp_path,
            "other-skill",
            {"name": "other-skill", "description": "No phase", "agent": "qa"},
        )
        reg = SkillRegistry(skills_dir=tmp_path)
        reg.discover()
        verify_skills = reg.filter_by_phase("verify")
        assert len(verify_skills) == 1
        assert verify_skills[0].name == "verify-skill"

    def test_filter_by_phase_returns_empty_when_no_match(self, tmp_path):
        _write_skill(tmp_path, "run-tests", _MIN)
        reg = SkillRegistry(skills_dir=tmp_path)
        reg.discover()
        assert reg.filter_by_phase("nonexistent-phase") == []


class TestSkillRegistryFilterByTags:
    def test_filter_by_tags_returns_matching_skills(self, tmp_path):
        _write_skill(
            tmp_path,
            "py-skill",
            {
                "name": "py-skill",
                "description": "Python skill",
                "agent": "qa",
                "tags": "python, testing",
            },
        )
        _write_skill(
            tmp_path,
            "go-skill",
            {
                "name": "go-skill",
                "description": "Go skill",
                "agent": "qa",
                "tags": "go, testing",
            },
        )
        reg = SkillRegistry(skills_dir=tmp_path)
        reg.discover()
        python_skills = reg.filter_by_tags(["python"])
        assert len(python_skills) == 1
        assert python_skills[0].name == "py-skill"

    def test_filter_by_tags_matches_any_tag(self, tmp_path):
        _write_skill(
            tmp_path,
            "py-skill",
            {
                "name": "py-skill",
                "description": "Python skill",
                "agent": "qa",
                "tags": "python, testing",
            },
        )
        reg = SkillRegistry(skills_dir=tmp_path)
        reg.discover()
        result = reg.filter_by_tags(["testing"])
        assert len(result) == 1

    def test_filter_by_tags_returns_empty_when_no_match(self, tmp_path):
        _write_skill(tmp_path, "run-tests", _MIN)
        reg = SkillRegistry(skills_dir=tmp_path)
        reg.discover()
        assert reg.filter_by_tags(["nonexistent-tag"]) == []


class TestSkillRegistryResolveTrigger:
    def test_resolve_trigger_matches_pattern(self, tmp_path):
        _write_skill(
            tmp_path,
            "run-tests",
            {
                "name": "run-tests",
                "description": "Tests",
                "agent": "qa",
                "triggers": "run tests, test this",
            },
        )
        reg = SkillRegistry(skills_dir=tmp_path)
        reg.discover()
        skill = reg.resolve_trigger("please run tests now")
        assert skill is not None
        assert skill.name == "run-tests"

    def test_resolve_trigger_case_insensitive(self, tmp_path):
        _write_skill(
            tmp_path,
            "run-tests",
            {
                "name": "run-tests",
                "description": "Tests",
                "agent": "qa",
                "triggers": "Run Tests",
            },
        )
        reg = SkillRegistry(skills_dir=tmp_path)
        reg.discover()
        skill = reg.resolve_trigger("run tests")
        assert skill is not None

    def test_resolve_trigger_returns_none_when_no_match(self, tmp_path):
        _write_skill(
            tmp_path,
            "run-tests",
            {
                "name": "run-tests",
                "description": "Tests",
                "agent": "qa",
                "triggers": "specific phrase",
            },
        )
        reg = SkillRegistry(skills_dir=tmp_path)
        reg.discover()
        assert reg.resolve_trigger("something completely different") is None

    def test_resolve_trigger_no_triggers_returns_none(self, tmp_path):
        _write_skill(tmp_path, "run-tests", _MIN)
        reg = SkillRegistry(skills_dir=tmp_path)
        reg.discover()
        assert reg.resolve_trigger("run tests") is None


class TestSkillRegistryValidateAll:
    def test_validate_all_returns_empty_when_valid(self, tmp_path):
        skills_dir = tmp_path / "skills"
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "qa-engineer.md").write_text("# QA Engineer")
        fm = {"name": "run-tests", "description": "Tests", "agent": "qa-engineer"}
        _write_skill(skills_dir, "run-tests", fm)
        reg = SkillRegistry(skills_dir=skills_dir, agents_dir=agents_dir)
        reg.discover()
        errors = reg.validate_all()
        assert errors == []

    def test_validate_all_returns_errors_for_missing_agent(self, tmp_path):
        skills_dir = tmp_path / "skills"
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        fm = {"name": "run-tests", "description": "Tests", "agent": "missing-agent"}
        _write_skill(skills_dir, "run-tests", fm)
        reg = SkillRegistry(skills_dir=skills_dir, agents_dir=agents_dir)
        reg.discover()
        errors = reg.validate_all()
        assert len(errors) == 1
        assert errors[0].skill_name == "run-tests"
        assert "missing-agent" in errors[0].message

    def test_validate_all_no_agents_dir_returns_empty(self, tmp_path):
        _write_skill(tmp_path, "run-tests", _MIN)
        reg = SkillRegistry(skills_dir=tmp_path)
        reg.discover()
        errors = reg.validate_all()
        assert errors == []


class TestSkillRegistryConflictResolution:
    def test_local_wins_over_builtin(self, tmp_path):
        skills_dir = tmp_path / "skills"
        # alpha-local: no source key => defaults to "local"
        _write_skill(
            skills_dir,
            "alpha-local",
            {"name": "shared-skill", "description": "Local version", "agent": "qa"},
        )
        _write_skill(
            skills_dir,
            "beta-builtin",
            {
                "name": "shared-skill",
                "description": "Builtin version",
                "agent": "qa",
                "source": "builtin",
            },
        )
        reg = SkillRegistry(skills_dir=skills_dir)
        reg.discover()
        skill = reg.get("shared-skill")
        assert skill is not None
        assert skill.description == "Local version"

    def test_builtin_wins_over_learning(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(
            skills_dir,
            "alpha-builtin",
            {
                "name": "shared-skill",
                "description": "Builtin version",
                "agent": "qa",
                "source": "builtin",
            },
        )
        _write_skill(
            skills_dir,
            "beta-learning",
            {
                "name": "shared-skill",
                "description": "Learning version",
                "agent": "qa",
                "source": "learning",
            },
        )
        reg = SkillRegistry(skills_dir=skills_dir)
        reg.discover()
        skill = reg.get("shared-skill")
        assert skill is not None
        assert skill.description == "Builtin version"

    def test_same_source_higher_priority_wins(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _write_skill(
            skills_dir,
            "alpha-low",
            {
                "name": "shared-skill",
                "description": "Low priority",
                "agent": "qa",
                "priority": "1",
            },
        )
        _write_skill(
            skills_dir,
            "beta-high",
            {
                "name": "shared-skill",
                "description": "High priority",
                "agent": "qa",
                "priority": "10",
            },
        )
        reg = SkillRegistry(skills_dir=skills_dir)
        reg.discover()
        skill = reg.get("shared-skill")
        assert skill is not None
        assert skill.description == "High priority"

    def test_same_source_same_priority_first_alphabetically_wins(self, tmp_path):
        skills_dir = tmp_path / "skills"
        # alpha-dir comes before beta-dir alphabetically
        _write_skill(
            skills_dir,
            "alpha-dir",
            {
                "name": "shared-skill",
                "description": "First alphabetically",
                "agent": "qa",
            },
        )
        _write_skill(
            skills_dir,
            "beta-dir",
            {
                "name": "shared-skill",
                "description": "Second alphabetically",
                "agent": "qa",
            },
        )
        reg = SkillRegistry(skills_dir=skills_dir)
        reg.discover()
        skill = reg.get("shared-skill")
        assert skill is not None
        assert skill.description == "First alphabetically"
