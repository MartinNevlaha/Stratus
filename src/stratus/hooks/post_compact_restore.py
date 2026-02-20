"""SessionStart[compact] hook: restore state after compaction."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def build_restore_message(session_dir: Path) -> str | None:
    """Build a context restoration message from saved pre-compact state.

    Returns None if no saved state exists.
    """
    state_file = session_dir / "pre-compact-state.json"
    if not state_file.exists():
        return None

    try:
        state = json.loads(state_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    parts = ["## Context Restored After Compaction\n"]

    captured_at = state.get("captured_at", "unknown")
    parts.append(f"State captured at: {captured_at}\n")

    plan_file = state.get("plan_file")
    if plan_file:
        parts.append(f"Active plan: {plan_file}")

    tasks = state.get("tasks", [])
    if tasks:
        parts.append(f"Tasks in progress: {', '.join(str(t) for t in tasks)}")

    spec_state = state.get("spec_state")
    if spec_state:
        parts.append("")  # blank line separator
        parts.append("### Spec Workflow State")
        phase = spec_state.get("phase", "unknown")
        parts.append(f"Phase: {phase}")
        slug = spec_state.get("slug")
        if slug:
            parts.append(f"Slug: {slug}")
        plan_path = spec_state.get("plan_path")
        if plan_path:
            parts.append(f"Plan: {plan_path}")
        worktree = spec_state.get("worktree")
        if worktree:
            parts.append(f"Worktree: {worktree.get('path', 'unknown')}")
            parts.append(f"Branch: {worktree.get('branch', 'unknown')}")
        completed = spec_state.get("completed_tasks", 0)
        total = spec_state.get("total_tasks", 0)
        if total > 0:
            parts.append(f"Progress: {completed}/{total} tasks")
        review_iter = spec_state.get("review_iteration", 0)
        if review_iter > 0:
            parts.append(f"Review iteration: {review_iter}")

    delivery_state = state.get("delivery_state")
    if delivery_state:
        parts.append("")
        parts.append("### Delivery State")
        phase = delivery_state.get("delivery_phase", "unknown")
        parts.append(f"Phase: {phase}")
        slug = delivery_state.get("slug")
        if slug:
            parts.append(f"Slug: {slug}")
        lead = delivery_state.get("phase_lead")
        if lead:
            parts.append(f"Lead: {lead}")
        mode = delivery_state.get("orchestration_mode")
        if mode:
            parts.append(f"Mode: {mode}")

    return "\n".join(parts)


def save_compact_summary(
    session_dir: Path,
    session_id: str,
    summary: str,
    timestamp: str,
    pre_tokens: int,
) -> None:
    """Save compact summary to memory API and file fallback."""
    try:
        import httpx

        from stratus.hooks._common import get_api_url

        api_url = get_api_url()
        httpx.post(
            f"{api_url}/api/memory/save",
            json={
                "text": summary,
                "title": f"Compact summary ({pre_tokens:,} tokens)",
                "type": "decision",
                "actor": "system",
                "tags": ["compact-summary"],
                "session_id": session_id,
                "dedupe_key": f"compact:{session_id}",
                "importance": 0.7,
            },
            timeout=2.0,
        )
    except Exception:
        pass

    session_dir.mkdir(parents=True, exist_ok=True)
    summary_file = (
        session_dir / f"compact-summary-{timestamp.replace(':', '-').replace('.', '-')}.txt"
    )
    try:
        summary_file.write_text(summary)
    except OSError:
        pass


def main() -> None:
    """Entry point for SessionStart[compact] hook."""
    from stratus.hooks._common import get_session_dir, read_hook_input
    from stratus.session.state import resolve_session_id
    from stratus.transcript import extract_compact_summaries

    hook_input = read_hook_input()
    session_id = hook_input.get("session_id") or resolve_session_id()
    session_dir = get_session_dir(session_id)

    message = build_restore_message(session_dir)
    if message:
        print(message)

    transcript_path = hook_input.get("transcript_path")
    if transcript_path:
        from pathlib import Path

        path = Path(transcript_path)
        if path.exists():
            events = extract_compact_summaries(path)
            if events:
                latest = events[-1]
                if latest.summary:
                    save_compact_summary(
                        session_dir,
                        session_id,
                        latest.summary,
                        latest.timestamp,
                        latest.pre_tokens,
                    )

    sys.exit(0)


if __name__ == "__main__":
    main()
