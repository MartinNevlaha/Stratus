"""TeammateIdle quality gate hook.

Validates that reviewer teammates produce properly formatted verdict output.
Exit 2 → reject (keep teammate working). Exit 0 → allow through.
NEVER crashes — all errors swallowed with exit 0.
"""

from __future__ import annotations

import re
import sys

_VERDICT_RE = re.compile(r"verdict\s*:\s*(pass|fail)", re.IGNORECASE)


def evaluate_idle(payload: dict[str, str]) -> tuple[int, str]:
    """Evaluate teammate idle output. Returns (exit_code, message)."""
    try:
        if not payload or not isinstance(payload, dict):
            return 0, ""

        output = payload.get("output")
        if output is None:
            return 0, ""

        # Only validate review-type teammates
        task_type = payload.get("task_type", "")
        if task_type and task_type != "review":
            return 0, ""

        if not output.strip():
            return 2, "Output is empty. Please provide a verdict."

        if not _VERDICT_RE.search(output):
            return 2, (
                "Output must contain 'Verdict: PASS' or 'Verdict: FAIL'. "
                "Please reformat your output."
            )

        return 0, ""
    except Exception:
        return 0, ""


def main() -> None:
    """Entry point for TeammateIdle hook."""
    from stratus.hooks._common import read_hook_input

    payload = read_hook_input()
    exit_code, msg = evaluate_idle(payload)
    if msg:
        print(msg, file=sys.stderr)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
