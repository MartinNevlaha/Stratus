"""PostToolUse hook: warn when implementation files are edited without a corresponding test."""

from __future__ import annotations

import fnmatch
import sys
from pathlib import Path

import httpx

from stratus.hooks._common import read_hook_input

WRITE_TOOLS = {"Write", "Edit"}

SKIP_PATTERNS = (
    "test_*.py",
    "*_test.py",
    "*.test.*",
    "*.spec.*",
    "conftest.py",
    "*.md",
    "*.json",
    "*.yaml",
    "*.yml",
    "*.toml",
    "*.txt",
    "*.cfg",
    "*.ini",
    "__init__.py",
    "__main__.py",
)


def is_skippable(file_path: str) -> bool:
    """Return True if this file should be excluded from TDD enforcement."""
    name = Path(file_path).name
    return any(fnmatch.fnmatch(name, pattern) for pattern in SKIP_PATTERNS)


def find_test_file(file_path: str, project_root: Path | None = None) -> Path | None:
    """Return the test file path if it exists, otherwise None.

    Maps src/.../foo.py → <project_root>/tests/test_foo.py.
    Only applies to .py files.
    """
    path = Path(file_path)
    if path.suffix != ".py":
        return None

    root = project_root if project_root is not None else Path.cwd()
    test_file = root / "tests" / f"test_{path.stem}.py"
    return test_file if test_file.exists() else None


def _record_missing_test(file_path: str) -> None:
    """Best-effort: record missing test to analytics."""
    try:
        from stratus.hooks._common import get_api_url

        api_url = get_api_url()
        httpx.post(
            f"{api_url}/api/learning/analytics/record-failure",
            json={
                "category": "missing_test",
                "file_path": file_path,
                "detail": f"No test file for {file_path}",
            },
            timeout=2.0,
        )
    except Exception:
        pass


def main() -> None:
    """Entry point for PostToolUse hook."""
    hook_input = read_hook_input()

    tool_name = hook_input.get("tool_name", "")
    if tool_name not in WRITE_TOOLS:
        sys.exit(0)

    tool_input = hook_input.get("tool_input") or {}
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    if is_skippable(file_path):
        sys.exit(0)

    # Only enforce for Python files
    if not file_path.endswith(".py"):
        sys.exit(0)

    test_path = find_test_file(file_path)
    if test_path is None:
        stem = Path(file_path).stem
        print(
            f"TDD WARNING: No test file found for '{file_path}'.\n"
            f"Expected: tests/test_{stem}.py\n"
            f"Write the test first (TDD) or create the missing test file.",
            file=sys.stderr,
        )
        _record_missing_test(file_path)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
