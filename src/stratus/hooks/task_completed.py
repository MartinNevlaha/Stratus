"""TaskCompleted quality gate hook.

Validates task completion output: reviews must have verdicts, implementation
tasks must not have failing tests. Exit 2 → reject. Exit 0 → allow through.
NEVER crashes — all errors swallowed with exit 0.
"""

from __future__ import annotations

import re
import sys

_VERDICT_RE = re.compile(r"verdict\s*:\s*(pass|fail)", re.IGNORECASE)
_TEST_FAIL_RE = re.compile(r"(\d+)\s+failed", re.IGNORECASE)


def evaluate_completion(payload: dict[str, str]) -> tuple[int, str]:
    """Evaluate task completion output. Returns (exit_code, message)."""
    try:
        if not payload or not isinstance(payload, dict):
            return 0, ""

        task_id: str = payload.get("task_id", "")
        if not task_id:
            return 0, ""

        output: str = payload.get("output", "")
        task_type: str = payload.get("task_type", "")

        # Review tasks must contain a verdict
        if task_type == "review":
            if not _VERDICT_RE.search(output):
                return 2, (
                    f"Review task {task_id} must contain 'Verdict: PASS' or "
                    f"'Verdict: FAIL'. Please reformat."
                )

        # Implementation tasks: check for test failures
        if task_type == "implementation":
            m = _TEST_FAIL_RE.search(output)
            if m and int(m.group(1)) > 0:
                return 2, (
                    f"Task {task_id} has test failures ({m.group(1)} failed). "
                    f"Please fix before completing."
                )

        return 0, ""
    except Exception:
        return 0, ""


def _run_invariant_check() -> None:
    """Best-effort invariant validation via HTTP API. Errors swallowed."""
    try:
        import httpx

        from stratus.hooks._common import get_api_url

        url = f"{get_api_url()}/api/rules/validate-invariants"
        resp = httpx.post(url, json={}, timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            violations = data.get("violations", [])
            for v in violations:
                msg = v.get("message", "")
                print(f"Invariant violation: {msg}", file=sys.stderr)
    except Exception:
        pass  # Best-effort — never block


def main() -> None:
    """Entry point for TaskCompleted hook."""
    from stratus.hooks._common import read_hook_input

    payload = read_hook_input()
    exit_code, msg = evaluate_completion(payload)
    if msg:
        print(msg, file=sys.stderr)

    # Best-effort invariant validation for implementation tasks
    task_type = payload.get("task_type", "") if isinstance(payload, dict) else ""
    if exit_code == 0 and task_type == "implementation":
        _run_invariant_check()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
