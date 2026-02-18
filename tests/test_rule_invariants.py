"""Tests for rule_engine/invariants.py — framework invariant definitions."""

from __future__ import annotations


class TestFrameworkInvariants:
    def test_has_six_entries(self):
        from stratus.rule_engine.invariants import FRAMEWORK_INVARIANTS

        assert len(FRAMEWORK_INVARIANTS) == 6

    def test_all_have_unique_ids(self):
        from stratus.rule_engine.invariants import FRAMEWORK_INVARIANTS

        ids = [inv.id for inv in FRAMEWORK_INVARIANTS]
        assert len(ids) == len(set(ids))

    def test_all_ids_start_with_inv(self):
        from stratus.rule_engine.invariants import FRAMEWORK_INVARIANTS

        for inv in FRAMEWORK_INVARIANTS:
            assert inv.id.startswith("inv-"), f"ID '{inv.id}' does not start with 'inv-'"

    def test_only_immutable_in_spec_is_non_disablable(self):
        from stratus.rule_engine.invariants import FRAMEWORK_INVARIANTS

        non_disablable = [inv for inv in FRAMEWORK_INVARIANTS if not inv.disablable]
        assert len(non_disablable) == 1
        assert non_disablable[0].id == "inv-rules-immutable-in-spec"

    def test_all_other_invariants_are_disablable(self):
        from stratus.rule_engine.invariants import FRAMEWORK_INVARIANTS

        disablable = [inv for inv in FRAMEWORK_INVARIANTS if inv.disablable]
        assert len(disablable) == 5

    def test_expected_ids_present(self):
        from stratus.rule_engine.invariants import FRAMEWORK_INVARIANTS

        ids = {inv.id for inv in FRAMEWORK_INVARIANTS}
        expected = {
            "inv-process-no-code",
            "inv-reviewers-readonly",
            "inv-engineering-quality-gates",
            "inv-no-new-deps",
            "inv-file-size-limit",
            "inv-rules-immutable-in-spec",
        }
        assert ids == expected

    def test_all_have_non_empty_titles(self):
        from stratus.rule_engine.invariants import FRAMEWORK_INVARIANTS

        for inv in FRAMEWORK_INVARIANTS:
            assert inv.title, f"Invariant '{inv.id}' has empty title"

    def test_all_have_non_empty_content(self):
        from stratus.rule_engine.invariants import FRAMEWORK_INVARIANTS

        for inv in FRAMEWORK_INVARIANTS:
            assert inv.content, f"Invariant '{inv.id}' has empty content"


class TestValidateAgainstInvariants:
    def test_returns_empty_list_when_no_violations(self):
        from stratus.rule_engine.invariants import (
            FRAMEWORK_INVARIANTS,
            validate_against_invariants,
        )

        result = validate_against_invariants(FRAMEWORK_INVARIANTS)
        assert result == []

    def test_returns_list_type(self):
        from stratus.rule_engine.invariants import (
            FRAMEWORK_INVARIANTS,
            validate_against_invariants,
        )

        result = validate_against_invariants(FRAMEWORK_INVARIANTS)
        assert isinstance(result, list)

    def test_accepts_empty_invariants_list(self):
        from stratus.rule_engine.invariants import validate_against_invariants

        result = validate_against_invariants([])
        assert result == []
