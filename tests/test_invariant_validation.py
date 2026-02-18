"""Tests for validate_against_invariants() — Phase 1.2 implementation."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from stratus.rule_engine.invariants import FRAMEWORK_INVARIANTS, validate_against_invariants
from stratus.rule_engine.models import (
    InvariantContext,
    Rule,
    RuleSource,
    RulesSnapshot,
)


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _file_invariant() -> object:
    return next(inv for inv in FRAMEWORK_INVARIANTS if inv.id == "inv-file-size-limit")


def _immutable_invariant() -> object:
    return next(inv for inv in FRAMEWORK_INVARIANTS if inv.id == "inv-rules-immutable-in-spec")


# ---------------------------------------------------------------------------
# 1. Backward compat: context=None returns []
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_validate_no_context_returns_empty():
    result = validate_against_invariants(FRAMEWORK_INVARIANTS, context=None)
    assert result == []


# ---------------------------------------------------------------------------
# 2. File size: hard limit (>500 lines)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_validate_file_size_hard_limit(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    big_file = src / "big_module.py"
    big_file.write_text("\n" * 501)  # 502 lines (empty lines including trailing)

    ctx = InvariantContext(project_root=tmp_path)
    invariants = [_file_invariant()]
    violations = validate_against_invariants(invariants, context=ctx)

    assert len(violations) == 1
    assert violations[0].invariant_id == "inv-file-size-limit"
    assert "hard limit" in violations[0].message.lower()
    assert violations[0].file_path is not None
    assert "big_module.py" in violations[0].file_path


# ---------------------------------------------------------------------------
# 3. File size: soft limit (>300 lines)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_validate_file_size_soft_limit(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    medium_file = src / "medium_module.py"
    medium_file.write_text("\n" * 301)  # 302 lines

    ctx = InvariantContext(project_root=tmp_path)
    invariants = [_file_invariant()]
    violations = validate_against_invariants(invariants, context=ctx)

    assert len(violations) == 1
    assert violations[0].invariant_id == "inv-file-size-limit"
    assert "soft limit" in violations[0].message.lower()


# ---------------------------------------------------------------------------
# 4. File size: test_ files are skipped
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_validate_file_size_skips_test_files(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    test_file = src / "test_big.py"
    test_file.write_text("\n" * 600)

    ctx = InvariantContext(project_root=tmp_path)
    invariants = [_file_invariant()]
    violations = validate_against_invariants(invariants, context=ctx)

    assert violations == []


# ---------------------------------------------------------------------------
# 5. File size: __init__.py is skipped
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_validate_file_size_skips_init(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    init_file = src / "__init__.py"
    init_file.write_text("\n" * 600)

    ctx = InvariantContext(project_root=tmp_path)
    invariants = [_file_invariant()]
    violations = validate_against_invariants(invariants, context=ctx)

    assert violations == []


# ---------------------------------------------------------------------------
# 6. File size: missing src/ dir returns no violations
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_validate_file_size_no_src_dir(tmp_path: Path):
    # No src/ directory created
    ctx = InvariantContext(project_root=tmp_path)
    invariants = [_file_invariant()]
    violations = validate_against_invariants(invariants, context=ctx)

    assert violations == []


# ---------------------------------------------------------------------------
# 7. Rules immutable: when spec_active=False, no check happens
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_validate_rules_immutable_no_spec(tmp_path: Path):
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "my-rule.md").write_text("# Rule\nDo stuff.")

    prev_content = "# Rule\nOld content."
    prev_snapshot = RulesSnapshot(
        rules=[
            Rule(
                name="my-rule",
                source=RuleSource.PROJECT,
                content=prev_content,
                path=str(rules_dir / "my-rule.md"),
                content_hash=_hash(prev_content),
            )
        ]
    )

    ctx = InvariantContext(
        project_root=tmp_path,
        previous_rules_snapshot=prev_snapshot,
        spec_active=False,  # spec NOT active
    )
    invariants = [_immutable_invariant()]
    violations = validate_against_invariants(invariants, context=ctx)

    assert violations == []


# ---------------------------------------------------------------------------
# 8. Rules immutable: spec_active=True with changed rule detects modification
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_validate_rules_immutable_detects_changes(tmp_path: Path):
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)

    # Current rule content (different from snapshot)
    current_content = "# Rule\nNew content that changed."
    (rules_dir / "my-rule.md").write_text(current_content)

    # Snapshot has old content
    prev_content = "# Rule\nOld content."
    prev_snapshot = RulesSnapshot(
        rules=[
            Rule(
                name="my-rule",
                source=RuleSource.PROJECT,
                content=prev_content,
                path=str(rules_dir / "my-rule.md"),
                content_hash=_hash(prev_content),
            )
        ]
    )

    ctx = InvariantContext(
        project_root=tmp_path,
        previous_rules_snapshot=prev_snapshot,
        spec_active=True,
    )
    invariants = [_immutable_invariant()]
    violations = validate_against_invariants(invariants, context=ctx)

    assert len(violations) == 1
    assert violations[0].invariant_id == "inv-rules-immutable-in-spec"
    assert violations[0].file_path is not None or violations[0].message


# ---------------------------------------------------------------------------
# 9. Disabled invariant is skipped
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_validate_disabled_invariant_skipped(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    big_file = src / "big_module.py"
    big_file.write_text("\n" * 501)

    ctx = InvariantContext(
        project_root=tmp_path,
        disabled_ids=["inv-file-size-limit"],
    )
    invariants = [_file_invariant()]
    violations = validate_against_invariants(invariants, context=ctx)

    # inv-file-size-limit is disablable=True, so it should be skipped
    assert violations == []


# ---------------------------------------------------------------------------
# 10. Non-disablable invariant cannot be disabled
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_validate_nondisablable_not_skipped(tmp_path: Path):
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)

    current_content = "# Rule\nNew content."
    (rules_dir / "my-rule.md").write_text(current_content)

    prev_content = "# Rule\nOld content."
    prev_snapshot = RulesSnapshot(
        rules=[
            Rule(
                name="my-rule",
                source=RuleSource.PROJECT,
                content=prev_content,
                path=str(rules_dir / "my-rule.md"),
                content_hash=_hash(prev_content),
            )
        ]
    )

    ctx = InvariantContext(
        project_root=tmp_path,
        previous_rules_snapshot=prev_snapshot,
        spec_active=True,
        disabled_ids=["inv-rules-immutable-in-spec"],  # try to disable non-disablable
    )
    # inv-rules-immutable-in-spec has disablable=False, so it must still run
    invariants = [_immutable_invariant()]
    violations = validate_against_invariants(invariants, context=ctx)

    assert len(violations) == 1
    assert violations[0].invariant_id == "inv-rules-immutable-in-spec"
