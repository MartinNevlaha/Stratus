"""Tests for skills/models.py — SkillManifest, SkillSource, SkillValidationError, SkillConflict."""

from __future__ import annotations

import pytest

from stratus.skills.models import (
    SkillConflict,
    SkillManifest,
    SkillSource,
    SkillValidationError,
)


class TestSkillSource:
    def test_has_three_values(self):
        values = list(SkillSource)
        assert len(values) == 3

    def test_local_value(self):
        assert SkillSource.LOCAL == "local"

    def test_builtin_value(self):
        assert SkillSource.BUILTIN == "builtin"

    def test_learning_value(self):
        assert SkillSource.LEARNING == "learning"

    def test_is_str_enum(self):
        from enum import StrEnum

        assert issubclass(SkillSource, StrEnum)

    def test_usable_as_string(self):
        assert str(SkillSource.LOCAL) == "local"
        assert f"{SkillSource.BUILTIN}" == "builtin"


class TestSkillManifest:
    def test_required_fields_only(self):
        m = SkillManifest(
            name="run-tests",
            description="Runs the project test suite.",
            agent="qa-engineer",
        )
        assert m.name == "run-tests"
        assert m.description == "Runs the project test suite."
        assert m.agent == "qa-engineer"

    def test_all_fields(self):
        m = SkillManifest(
            name="my-skill",
            description="Does something",
            agent="framework-expert",
            context="inline",
            version="1.2.3",
            requires=["other-skill"],
            triggers=["run my skill"],
            priority=5,
            tags=["testing", "python"],
            requires_phase="verify",
            source="builtin",
            min_framework_version="0.5.0",
            body="Do the thing.",
            path="/some/path/SKILL.md",
            content_hash="abc123",
        )
        assert m.context == "inline"
        assert m.version == "1.2.3"
        assert m.requires == ["other-skill"]
        assert m.triggers == ["run my skill"]
        assert m.priority == 5
        assert m.tags == ["testing", "python"]
        assert m.requires_phase == "verify"
        assert m.source == "builtin"
        assert m.min_framework_version == "0.5.0"
        assert m.body == "Do the thing."
        assert m.path == "/some/path/SKILL.md"
        assert m.content_hash == "abc123"

    def test_default_context(self):
        m = SkillManifest(name="x", description="d", agent="a")
        assert m.context == "fork"

    def test_default_version_none(self):
        m = SkillManifest(name="x", description="d", agent="a")
        assert m.version is None

    def test_default_requires_empty_list(self):
        m = SkillManifest(name="x", description="d", agent="a")
        assert m.requires == []

    def test_default_triggers_empty_list(self):
        m = SkillManifest(name="x", description="d", agent="a")
        assert m.triggers == []

    def test_default_priority_zero(self):
        m = SkillManifest(name="x", description="d", agent="a")
        assert m.priority == 0

    def test_default_tags_empty_list(self):
        m = SkillManifest(name="x", description="d", agent="a")
        assert m.tags == []

    def test_default_requires_phase_none(self):
        m = SkillManifest(name="x", description="d", agent="a")
        assert m.requires_phase is None

    def test_default_source_local(self):
        m = SkillManifest(name="x", description="d", agent="a")
        assert m.source == "local"

    def test_default_min_framework_version_none(self):
        m = SkillManifest(name="x", description="d", agent="a")
        assert m.min_framework_version is None

    def test_default_body_empty_string(self):
        m = SkillManifest(name="x", description="d", agent="a")
        assert m.body == ""

    def test_default_path_empty_string(self):
        m = SkillManifest(name="x", description="d", agent="a")
        assert m.path == ""

    def test_default_content_hash_empty_string(self):
        m = SkillManifest(name="x", description="d", agent="a")
        assert m.content_hash == ""

    def test_requires_is_not_shared_across_instances(self):
        m1 = SkillManifest(name="x", description="d", agent="a")
        m2 = SkillManifest(name="y", description="d", agent="a")
        m1.requires.append("something")
        assert m2.requires == []

    def test_tags_is_not_shared_across_instances(self):
        m1 = SkillManifest(name="x", description="d", agent="a")
        m2 = SkillManifest(name="y", description="d", agent="a")
        m1.tags.append("python")
        assert m2.tags == []


class TestSkillValidationError:
    def test_creation(self):
        err = SkillValidationError(skill_name="my-skill", message="Agent not found")
        assert err.skill_name == "my-skill"
        assert err.message == "Agent not found"

    def test_fields_required(self):
        with pytest.raises(Exception):
            SkillValidationError(skill_name="x")  # type: ignore[call-arg]


class TestSkillConflict:
    def test_creation(self):
        conflict = SkillConflict(
            name="my-skill",
            sources=["local", "builtin"],
            winner="local",
        )
        assert conflict.name == "my-skill"
        assert conflict.sources == ["local", "builtin"]
        assert conflict.winner == "local"
