"""Tests for rule_engine/index.py — RulesIndex loading and immutability checks."""

from __future__ import annotations

from pathlib import Path

from stratus.rule_engine.models import (
    RuleSource,
    RulesSnapshot,
)


class TestRulesIndexInit:
    def test_accepts_project_root(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex

        idx = RulesIndex(project_root=tmp_path)
        assert idx._project_root == tmp_path

    def test_default_rules_dir(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex

        idx = RulesIndex(project_root=tmp_path)
        assert idx._rules_dir == tmp_path / ".claude" / "rules"

    def test_custom_rules_dir(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex

        custom = tmp_path / "custom-rules"
        idx = RulesIndex(project_root=tmp_path, rules_dir=custom)
        assert idx._rules_dir == custom


class TestRulesIndexLoad:
    def test_returns_rules_snapshot(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex

        idx = RulesIndex(project_root=tmp_path)
        result = idx.load()
        assert isinstance(result, RulesSnapshot)

    def test_loads_rules_from_rules_dir(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex

        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "my-rule.md").write_text("# My Rule\nDo things.")

        idx = RulesIndex(project_root=tmp_path)
        snapshot = idx.load()

        assert len(snapshot.rules) == 1
        assert snapshot.rules[0].name == "my-rule"
        assert snapshot.rules[0].source == RuleSource.PROJECT
        assert "Do things." in snapshot.rules[0].content

    def test_loads_multiple_rules_sorted(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex

        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "beta.md").write_text("# Beta")
        (rules_dir / "alpha.md").write_text("# Alpha")
        (rules_dir / "gamma.md").write_text("# Gamma")

        idx = RulesIndex(project_root=tmp_path)
        snapshot = idx.load()

        names = [r.name for r in snapshot.rules]
        assert names == ["alpha", "beta", "gamma"]

    def test_includes_claude_md(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex

        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Project Instructions\nFollow these rules.")

        idx = RulesIndex(project_root=tmp_path)
        snapshot = idx.load()

        claude_rules = [r for r in snapshot.rules if r.source == RuleSource.CLAUDE_MD]
        assert len(claude_rules) == 1
        assert claude_rules[0].name == "CLAUDE"
        assert "Follow these rules." in claude_rules[0].content

    def test_claude_md_path_set_correctly(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex

        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("content")

        idx = RulesIndex(project_root=tmp_path)
        snapshot = idx.load()

        claude_rules = [r for r in snapshot.rules if r.source == RuleSource.CLAUDE_MD]
        assert claude_rules[0].path == str(claude_md)

    def test_computes_sha256_content_hash(self, tmp_path):
        import hashlib

        from stratus.rule_engine.index import RulesIndex

        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        content = "# Rule\nDo X."
        (rules_dir / "test.md").write_text(content)

        idx = RulesIndex(project_root=tmp_path)
        snapshot = idx.load()

        expected_hash = hashlib.sha256(content.encode()).hexdigest()
        assert snapshot.rules[0].content_hash == expected_hash

    def test_computes_snapshot_hash(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex

        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "a.md").write_text("content")

        idx = RulesIndex(project_root=tmp_path)
        snapshot = idx.load()

        assert snapshot.snapshot_hash != ""
        assert len(snapshot.snapshot_hash) == 64  # SHA256 hex digest

    def test_empty_snapshot_when_no_rules_dir(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex

        idx = RulesIndex(project_root=tmp_path)
        snapshot = idx.load()

        project_rules = [r for r in snapshot.rules if r.source == RuleSource.PROJECT]
        assert project_rules == []

    def test_empty_snapshot_when_rules_dir_missing(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex

        idx = RulesIndex(project_root=tmp_path, rules_dir=tmp_path / "nonexistent")
        snapshot = idx.load()

        assert snapshot.rules == []

    def test_no_claude_md_skipped(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex

        idx = RulesIndex(project_root=tmp_path)
        snapshot = idx.load()

        claude_rules = [r for r in snapshot.rules if r.source == RuleSource.CLAUDE_MD]
        assert claude_rules == []

    def test_rule_path_is_absolute_string(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex

        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "x.md").write_text("x")

        idx = RulesIndex(project_root=tmp_path)
        snapshot = idx.load()

        assert Path(snapshot.rules[0].path).is_absolute()


class TestCheckImmutability:
    def test_no_violations_when_unchanged(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex

        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "rule.md").write_text("content")

        idx = RulesIndex(project_root=tmp_path)
        previous = idx.load()
        violations = idx.check_immutability(previous)

        assert violations == []

    def test_detects_added_rule(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex

        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "existing.md").write_text("content")

        idx = RulesIndex(project_root=tmp_path)
        previous = idx.load()

        # Add a new rule
        (rules_dir / "new-rule.md").write_text("new content")
        violations = idx.check_immutability(previous)

        assert len(violations) == 1
        assert violations[0].rule_name == "new-rule"
        assert violations[0].change_type == "added"

    def test_detects_removed_rule(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex

        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        rule_file = rules_dir / "old-rule.md"
        rule_file.write_text("content")

        idx = RulesIndex(project_root=tmp_path)
        previous = idx.load()

        # Remove the rule
        rule_file.unlink()
        violations = idx.check_immutability(previous)

        assert len(violations) == 1
        assert violations[0].rule_name == "old-rule"
        assert violations[0].change_type == "removed"

    def test_detects_modified_rule(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex

        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        rule_file = rules_dir / "rule.md"
        rule_file.write_text("original content")

        idx = RulesIndex(project_root=tmp_path)
        previous = idx.load()

        # Modify the rule
        rule_file.write_text("changed content")
        violations = idx.check_immutability(previous)

        assert len(violations) == 1
        assert violations[0].rule_name == "rule"
        assert violations[0].change_type == "modified"

    def test_no_violations_empty_snapshot(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex

        idx = RulesIndex(project_root=tmp_path)
        previous = RulesSnapshot()
        violations = idx.check_immutability(previous)

        assert violations == []


class TestRefresh:
    def test_refresh_returns_updated_snapshot(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex

        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)

        idx = RulesIndex(project_root=tmp_path)
        first = idx.load()

        (rules_dir / "new.md").write_text("new rule")
        refreshed = idx.refresh()

        assert len(refreshed.rules) > len(first.rules)

    def test_refresh_is_same_as_load(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex

        idx = RulesIndex(project_root=tmp_path)
        load_result = idx.load()
        refresh_result = idx.refresh()

        assert load_result.snapshot_hash == refresh_result.snapshot_hash


class TestGetActiveInvariants:
    def test_returns_all_when_none_disabled(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex
        from stratus.rule_engine.invariants import FRAMEWORK_INVARIANTS

        idx = RulesIndex(project_root=tmp_path)
        active = idx.get_active_invariants()

        assert len(active) == len(FRAMEWORK_INVARIANTS)

    def test_excludes_disabled_disablable_invariants(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex

        idx = RulesIndex(project_root=tmp_path)
        active = idx.get_active_invariants(disabled_ids=["inv-process-no-code"])

        ids = [inv.id for inv in active]
        assert "inv-process-no-code" not in ids

    def test_never_excludes_non_disablable(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex

        idx = RulesIndex(project_root=tmp_path)
        # Try to disable the non-disablable invariant
        active = idx.get_active_invariants(disabled_ids=["inv-rules-immutable-in-spec"])

        ids = [inv.id for inv in active]
        assert "inv-rules-immutable-in-spec" in ids

    def test_none_disabled_ids_returns_all(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex
        from stratus.rule_engine.invariants import FRAMEWORK_INVARIANTS

        idx = RulesIndex(project_root=tmp_path)
        active = idx.get_active_invariants(disabled_ids=None)

        assert len(active) == len(FRAMEWORK_INVARIANTS)

    def test_empty_disabled_ids_returns_all(self, tmp_path):
        from stratus.rule_engine.index import RulesIndex
        from stratus.rule_engine.invariants import FRAMEWORK_INVARIANTS

        idx = RulesIndex(project_root=tmp_path)
        active = idx.get_active_invariants(disabled_ids=[])

        assert len(active) == len(FRAMEWORK_INVARIANTS)
