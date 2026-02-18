"""Tests for rule_engine/models.py — Pydantic models and enums."""

from __future__ import annotations

from stratus.rule_engine.models import (
    ImmutabilityViolation,
    Invariant,
    Rule,
    RuleSource,
    RulesSnapshot,
)


class TestRuleSourceEnum:
    def test_has_four_values(self):
        assert len(RuleSource) == 4

    def test_project_value(self):
        assert RuleSource.PROJECT == "project"

    def test_claude_md_value(self):
        assert RuleSource.CLAUDE_MD == "claude_md"

    def test_framework_value(self):
        assert RuleSource.FRAMEWORK == "framework"

    def test_learning_value(self):
        assert RuleSource.LEARNING == "learning"

    def test_is_str_enum(self):
        from enum import StrEnum

        assert issubclass(RuleSource, StrEnum)

    def test_string_comparison(self):
        assert RuleSource.PROJECT == "project"
        assert str(RuleSource.FRAMEWORK) == "framework"


class TestRuleModel:
    def test_creation_with_all_fields(self):
        rule = Rule(
            name="test-rule",
            source=RuleSource.PROJECT,
            content="## Rule\nAlways write tests.",
            path="/project/.claude/rules/test-rule.md",
            content_hash="abc123",
        )
        assert rule.name == "test-rule"
        assert rule.source == RuleSource.PROJECT
        assert rule.content == "## Rule\nAlways write tests."
        assert rule.path == "/project/.claude/rules/test-rule.md"
        assert rule.content_hash == "abc123"

    def test_content_hash_defaults_to_empty(self):
        rule = Rule(
            name="test-rule",
            source=RuleSource.CLAUDE_MD,
            content="content",
            path="/project/CLAUDE.md",
        )
        assert rule.content_hash == ""

    def test_all_sources_accepted(self):
        for source in RuleSource:
            rule = Rule(name="r", source=source, content="c", path="/p")
            assert rule.source == source

    def test_is_pydantic_model(self):
        from pydantic import BaseModel

        assert issubclass(Rule, BaseModel)


class TestRulesSnapshotModel:
    def test_creation_with_rules_and_hash(self):
        rule = Rule(name="r", source=RuleSource.PROJECT, content="c", path="/p")
        snapshot = RulesSnapshot(rules=[rule], snapshot_hash="deadbeef")
        assert len(snapshot.rules) == 1
        assert snapshot.snapshot_hash == "deadbeef"

    def test_empty_rules_list(self):
        snapshot = RulesSnapshot()
        assert snapshot.rules == []
        assert snapshot.snapshot_hash == ""

    def test_default_snapshot_hash_empty(self):
        snapshot = RulesSnapshot(rules=[])
        assert snapshot.snapshot_hash == ""

    def test_rules_preserved(self):
        rules = [
            Rule(name="r1", source=RuleSource.PROJECT, content="c1", path="/p1"),
            Rule(name="r2", source=RuleSource.LEARNING, content="c2", path="/p2"),
        ]
        snapshot = RulesSnapshot(rules=rules, snapshot_hash="h")
        assert snapshot.rules[0].name == "r1"
        assert snapshot.rules[1].name == "r2"


class TestInvariantModel:
    def test_creation_with_all_fields(self):
        inv = Invariant(
            id="inv-test",
            title="Test Invariant",
            content="No code in process roles.",
            disablable=False,
        )
        assert inv.id == "inv-test"
        assert inv.title == "Test Invariant"
        assert inv.content == "No code in process roles."
        assert inv.disablable is False

    def test_disablable_defaults_to_true(self):
        inv = Invariant(id="inv-x", title="X", content="content")
        assert inv.disablable is True

    def test_is_pydantic_model(self):
        from pydantic import BaseModel

        assert issubclass(Invariant, BaseModel)


class TestImmutabilityViolationModel:
    def test_creation_with_all_fields(self):
        violation = ImmutabilityViolation(
            rule_name="my-rule",
            change_type="modified",
            details="Rule content changed from X to Y",
        )
        assert violation.rule_name == "my-rule"
        assert violation.change_type == "modified"
        assert violation.details == "Rule content changed from X to Y"

    def test_creation_added(self):
        violation = ImmutabilityViolation(rule_name="new-rule", change_type="added")
        assert violation.change_type == "added"
        assert violation.details == ""

    def test_creation_removed(self):
        violation = ImmutabilityViolation(rule_name="old-rule", change_type="removed")
        assert violation.change_type == "removed"

    def test_details_defaults_to_empty(self):
        violation = ImmutabilityViolation(rule_name="r", change_type="added")
        assert violation.details == ""

    def test_is_pydantic_model(self):
        from pydantic import BaseModel

        assert issubclass(ImmutabilityViolation, BaseModel)
