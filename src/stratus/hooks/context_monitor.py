"""PostToolUse hook: monitor context usage via transcript analysis."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

from stratus.session.config import (
    COMPACTION_THRESHOLD_PCT,
    THRESHOLD_AUTOCOMPACT,
    THRESHOLD_WARN,
    THROTTLE_MIN_INTERVAL_SEC,
)
from stratus.transcript import estimate_context_pct, parse_transcript, to_effective_pct


def should_throttle(cache_file: Path, threshold_pct: float) -> bool:
    """Check if we should skip this check based on throttle interval.

    Returns False (don't throttle) if:
    - No cache file exists (first run)
    - Enough time has passed since last check
    - Context is above warn threshold (always check when high)
    """
    try:
        data = json.loads(cache_file.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return False

    last_time = data.get("last_check_time", 0)
    elapsed = time.time() - last_time

    # Always check when above warning threshold
    if threshold_pct >= THRESHOLD_WARN:
        return False

    return elapsed < THROTTLE_MIN_INTERVAL_SEC


def check_context_usage(
    transcript_path: Path,
    *,
    cache_dir: Path | None = None,
    context_window: int = 200_000,
) -> str | None:
    """Analyze transcript and return warning message if context is high.

    Returns None if context is below warning threshold.
    Returns warning string if at or above 65%.
    """
    stats = parse_transcript(transcript_path)
    if not stats.usages:
        return None

    current = stats.final_tokens
    raw_pct = estimate_context_pct(current, context_window=context_window)
    eff_pct = to_effective_pct(raw_pct, threshold=COMPACTION_THRESHOLD_PCT)

    # Update cache
    if cache_dir:
        cache_file = cache_dir / "context-cache.json"
        if should_throttle(cache_file, raw_pct):
            return None
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(
            json.dumps(
                {
                    "last_check_time": time.time(),
                    "last_pct": raw_pct,
                }
            )
        )

    if raw_pct >= THRESHOLD_AUTOCOMPACT:
        return (
            f"⚠ CONTEXT CRITICAL: {raw_pct:.1f}% raw ({eff_pct:.1f}% effective). "
            f"Compaction imminent at {COMPACTION_THRESHOLD_PCT}%. "
            f"Save important context now."
        )
    elif raw_pct >= THRESHOLD_WARN:
        return (
            f"⚡ Context at {raw_pct:.1f}% raw ({eff_pct:.1f}% effective). "
            f"Consider saving important findings to memory."
        )

    return None


def _record_context_overflow(warning: str) -> None:
    """Best-effort: record context overflow to analytics."""
    try:
        from stratus.hooks._common import get_api_url

        api_url = get_api_url()
        httpx.post(
            f"{api_url}/api/learning/analytics/record-failure",
            json={"category": "context_overflow", "detail": warning[:500]},
            timeout=2.0,
        )
    except Exception:
        pass


def main() -> None:
    """Entry point for PostToolUse hook."""
    from stratus.hooks._common import read_hook_input

    hook_input = read_hook_input()
    transcript_path = hook_input.get("transcript_path")
    if not transcript_path:
        sys.exit(0)

    path = Path(transcript_path)
    if not path.exists():
        sys.exit(0)

    from stratus.session.config import get_data_dir

    cache_dir = get_data_dir()

    warning = check_context_usage(path, cache_dir=cache_dir)
    if warning:
        print(warning, file=sys.stderr)
        _record_context_overflow(warning)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
