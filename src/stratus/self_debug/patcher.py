"""Unified diff generation for self-debug sandbox."""

from __future__ import annotations

import difflib
from pathlib import Path

from stratus.self_debug.models import (
    GovernanceImpact,
    Issue,
    IssueType,
    PatchProposal,
    RiskLevel,
)

# Only these issue types get auto-patches; all others are report-only
_PATCHABLE_TYPES: frozenset[IssueType] = frozenset(
    {
        IssueType.BARE_EXCEPT,
        IssueType.UNUSED_IMPORT,
    }
)

# Paths where UNUSED_IMPORT patches are unsafe (re-exports, side-effects)
_IMPORT_PATCH_UNSAFE: frozenset[str] = frozenset(
    {
        "__init__",
        "hooks/",
        "registry/",
    }
)

_GOVERNANCE_DENYLIST: frozenset[str] = frozenset(
    {
        ".claude/",
        ".ai-framework.json",
        ".github/",
    }
)


def generate_patch(
    issue: Issue,
    original_source: str,
    max_lines: int = 200,
    project_root: Path | None = None,
) -> PatchProposal | None:
    """Generate a patch for an issue. Returns None if not patchable or too risky."""
    if issue.type not in _PATCHABLE_TYPES:
        return None

    gov_impact = _check_governance_impact(issue.file_path, _GOVERNANCE_DENYLIST)
    if gov_impact == GovernanceImpact.CRITICAL:
        return None

    if issue.type == IssueType.UNUSED_IMPORT:
        if any(seg in issue.file_path for seg in _IMPORT_PATCH_UNSAFE):
            return None

    fixed_source = _apply_fix(issue, original_source)
    if fixed_source is None or fixed_source == original_source:
        return None

    original_lines = original_source.splitlines(keepends=True)
    fixed_lines = fixed_source.splitlines(keepends=True)
    diff_lines = list(
        difflib.unified_diff(
            original_lines,
            fixed_lines,
            fromfile=f"a/{issue.file_path}",
            tofile=f"b/{issue.file_path}",
        )
    )

    if not diff_lines:
        return None

    unified_diff = "".join(diff_lines)
    diff_line_count = len(diff_lines)

    if diff_line_count > max_lines:
        return None

    risk = _compute_risk(issue, diff_line_count)
    tests = _find_affected_tests(issue.file_path, project_root) if project_root else []

    return PatchProposal(
        issue_id=issue.id,
        file_path=issue.file_path,
        unified_diff=unified_diff,
        risk=risk,
        governance_impact=gov_impact,
        tests_affected=tests,
    )


def _apply_fix(issue: Issue, source: str) -> str | None:
    """Apply a fix for the given issue type. Returns modified source or None."""
    lines = source.splitlines(keepends=True)

    if issue.type == IssueType.BARE_EXCEPT:
        return _fix_bare_except(lines, issue.line_start)
    elif issue.type == IssueType.UNUSED_IMPORT:
        return _fix_unused_import(lines, issue.line_start)
    return None


def _fix_bare_except(lines: list[str], line_num: int) -> str:
    """Replace 'except:' with 'except Exception:'."""
    idx = line_num - 1
    if idx < 0 or idx >= len(lines):
        return "".join(lines)
    lines[idx] = lines[idx].replace("except:", "except Exception:", 1)
    return "".join(lines)


def _fix_unused_import(lines: list[str], line_num: int) -> str:
    """Remove the import line."""
    idx = line_num - 1
    if idx < 0 or idx >= len(lines):
        return "".join(lines)
    return "".join(lines[:idx] + lines[idx + 1 :])


def _compute_risk(issue: Issue, diff_line_count: int) -> RiskLevel:
    """Compute risk level based on issue type and diff size."""
    if diff_line_count > 20:
        return RiskLevel.HIGH
    if issue.type in (IssueType.BARE_EXCEPT, IssueType.UNUSED_IMPORT):
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _check_governance_impact(
    file_path: str,
    governance_denylist: frozenset[str],
) -> GovernanceImpact:
    """Check if file is in governance-protected path."""
    for pattern in governance_denylist:
        if pattern in file_path:
            return GovernanceImpact.CRITICAL
    return GovernanceImpact.NONE


def _find_affected_tests(file_path: str, project_root: Path | None) -> list[str]:
    """Scan test directory for files that reference the given file's module."""
    if project_root is None:
        return []

    tests_dir = project_root / "tests"
    if not tests_dir.is_dir():
        return []

    stem = Path(file_path).stem
    affected: list[str] = []

    for test_file in tests_dir.iterdir():
        if not test_file.name.endswith(".py"):
            continue
        try:
            if stem in test_file.read_text():
                affected.append(test_file.name)
        except OSError:
            continue

    return sorted(affected)
