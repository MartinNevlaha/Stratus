"""Static analysis via stdlib ast for self-debug sandbox."""

from __future__ import annotations

import ast
import os
from pathlib import Path

from stratus.self_debug.models import Issue, IssueType


def analyze_file(source: str, file_path: str) -> list[Issue]:
    """Analyze a single Python file for issues. Returns empty list on parse failure."""
    if not source.strip():
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    issues: list[Issue] = []
    issues.extend(_detect_bare_excepts(tree, file_path))
    issues.extend(_detect_unused_imports(tree, file_path))
    issues.extend(_detect_missing_return_types(tree, file_path))
    return issues


def analyze_directory(
    root: Path,
    allowed_prefixes: frozenset[str],
    denied_prefixes: frozenset[str],
) -> tuple[list[Issue], int, int]:
    """Walk directory tree, analyzing .py files respecting prefix constraints.

    Returns (issues, analyzed_count, skipped_count).
    """
    issues: list[Issue] = []
    analyzed = 0
    skipped = 0

    if not root.is_dir():
        return issues, analyzed, skipped

    for dirpath, _dirnames, filenames in os.walk(root):
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            full_path = Path(dirpath) / fname
            rel_path = str(full_path.relative_to(root))

            if allowed_prefixes and not any(rel_path.startswith(p) for p in allowed_prefixes):
                skipped += 1
                continue

            if any(rel_path.startswith(p) for p in denied_prefixes):
                skipped += 1
                continue

            try:
                source = full_path.read_text()
            except (OSError, UnicodeDecodeError):
                skipped += 1
                continue

            issues.extend(analyze_file(source, rel_path))
            analyzed += 1

    return issues, analyzed, skipped


def _make_issue_id(file_path: str, line: int, issue_type: IssueType) -> str:
    return f"{file_path}:{line}:{issue_type.value}"


def _detect_bare_excepts(tree: ast.Module, file_path: str) -> list[Issue]:
    """Detect bare except: clauses (no exception type specified)."""
    issues: list[Issue] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            line = node.lineno
            issues.append(
                Issue(
                    id=_make_issue_id(file_path, line, IssueType.BARE_EXCEPT),
                    type=IssueType.BARE_EXCEPT,
                    file_path=file_path,
                    line_start=line,
                    line_end=node.end_lineno or line,
                    description=(
                        f"Bare except clause at line {line}. "
                        "Catches all exceptions including SystemExit and KeyboardInterrupt."
                    ),
                    suggestion=(
                        "Replace with 'except Exception:' to avoid catching"
                        " SystemExit/KeyboardInterrupt."
                    ),
                )
            )
    return issues


def _detect_unused_imports(tree: ast.Module, file_path: str) -> list[Issue]:
    """Detect unused imports with safety guards."""
    if file_path.endswith("__init__.py"):
        return []

    used_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            root: ast.expr = node
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name):
                used_names.add(root.id)

    type_checking_ranges = _get_type_checking_ranges(tree)

    issues: list[Issue] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if _in_type_checking(node, type_checking_ranges):
                continue
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                if name not in used_names:
                    line = node.lineno
                    issues.append(
                        Issue(
                            id=_make_issue_id(file_path, line, IssueType.UNUSED_IMPORT),
                            type=IssueType.UNUSED_IMPORT,
                            file_path=file_path,
                            line_start=line,
                            line_end=node.end_lineno or line,
                            description=f"Unused import: '{alias.name}' at line {line}.",
                            suggestion=f"Remove unused import '{alias.name}'.",
                        )
                    )

        elif isinstance(node, ast.ImportFrom):
            if _in_type_checking(node, type_checking_ranges):
                continue
            if node.module == "__future__":
                continue
            for alias in node.names:
                name = alias.asname or alias.name
                if name == "*":
                    continue
                if name not in used_names:
                    line = node.lineno
                    issues.append(
                        Issue(
                            id=_make_issue_id(file_path, line, IssueType.UNUSED_IMPORT),
                            type=IssueType.UNUSED_IMPORT,
                            file_path=file_path,
                            line_start=line,
                            line_end=node.end_lineno or line,
                            description=(
                                f"Unused import: '{name}' from"
                                f" '{node.module or ''}' at line {line}."
                            ),
                            suggestion=f"Remove unused import '{name}'.",
                        )
                    )

    return issues


def _get_type_checking_ranges(tree: ast.Module) -> list[tuple[int, int]]:
    """Find line ranges of `if TYPE_CHECKING:` blocks."""
    ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test = node.test
            is_tc = (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
                isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
            )
            if is_tc:
                start = node.lineno
                end = node.end_lineno or start
                ranges.append((start, end))
    return ranges


def _in_type_checking(node: ast.AST, ranges: list[tuple[int, int]]) -> bool:
    """Return True if the node's line falls within any TYPE_CHECKING block."""
    line = getattr(node, "lineno", 0)
    return any(start <= line <= end for start, end in ranges)


def _detect_missing_return_types(tree: ast.Module, file_path: str) -> list[Issue]:
    """Detect public functions missing return type annotations."""
    issues: list[Issue] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue
        if node.returns is not None:
            continue
        line = node.lineno
        issues.append(
            Issue(
                id=_make_issue_id(file_path, line, IssueType.MISSING_TYPE_HINT),
                type=IssueType.MISSING_TYPE_HINT,
                file_path=file_path,
                line_start=line,
                line_end=line,
                description=(
                    f"Public function '{node.name}' at line {line} missing return type annotation."
                ),
                suggestion=(
                    "Add return type annotation. "
                    "Report-only — no auto-patch generated for type hints."
                ),
            )
        )
    return issues
