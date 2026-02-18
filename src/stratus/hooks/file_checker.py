"""PostToolUse hook: run language-specific linting after Write/Edit tool calls."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import httpx

_TIMEOUT = 10  # seconds per command

_EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "typescript",
    ".jsx": "typescript",
    ".go": "go",
}


def detect_language(file_path: str) -> str | None:
    """Return the language key for a file path, or None if unsupported."""
    suffix = Path(file_path).suffix.lower()
    return _EXTENSION_MAP.get(suffix)


def _run_cmd(cmd: list[str]) -> tuple[int, str]:
    """Run a command, return (returncode, combined output). Skip if not installed."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
        output = (result.stdout + result.stderr).strip()
        return result.returncode, output
    except FileNotFoundError:
        return 0, ""  # tool not installed — skip silently


def run_linters(file_path: str, language: str) -> list[str]:
    """Run linters for the given language. Return list of error messages."""
    errors: list[str] = []

    if language == "python":
        commands = [
            (["ruff", "check", "--fix", file_path], True),
            (["ruff", "format", file_path], False),
            (["basedpyright", file_path], True),
        ]
    elif language == "typescript":
        commands = [
            (["eslint", "--fix", file_path], True),
            (["prettier", "--write", file_path], False),
            (["tsc", "--noEmit", file_path], True),
        ]
    elif language == "go":
        commands = [
            (["gofmt", "-w", file_path], False),
            (["golangci-lint", "run", file_path], True),
        ]
    else:
        return []

    for cmd, report_errors in commands:
        returncode, output = _run_cmd(cmd)
        if report_errors and returncode != 0:
            label = cmd[0]
            msg = f"{label}: {output}" if output else f"{label}: exited with code {returncode}"
            errors.append(msg)

    return errors


def _record_lint_failures(file_path: str, errors: list[str]) -> None:
    """Best-effort: record lint failures to analytics."""
    try:
        from stratus.hooks._common import get_api_url

        api_url = get_api_url()
        detail = "; ".join(e[:100] for e in errors)[:500]
        httpx.post(
            f"{api_url}/api/learning/analytics/record-failure",
            json={"category": "lint_error", "file_path": file_path, "detail": detail},
            timeout=2.0,
        )
    except Exception:
        pass


def main() -> None:
    """Entry point for PostToolUse hook."""
    from stratus.hooks._common import read_hook_input

    hook_input = read_hook_input()
    tool_name = hook_input.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    tool_input = hook_input.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    language = detect_language(file_path)
    if language is None:
        sys.exit(0)

    errors = run_linters(file_path, language)
    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        _record_lint_failures(file_path, errors)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
