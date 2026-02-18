"""Statusline output for Claude Code CLI."""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime

import httpx

from stratus.session.config import DEFAULT_PORT


def format_stratus_section(stratus_state: dict | None) -> str:
    """Format the stratus status segment from dashboard state."""
    if stratus_state is None:
        return "offline"

    orch = stratus_state.get("orchestration", {})
    mode = orch.get("mode", "inactive")

    if mode == "inactive":
        return "inactive"

    spec = orch.get("spec")
    if mode == "spec" and spec:
        phase = spec.get("phase", "?")
        slug = spec.get("slug", "")
        completed = spec.get("completed_tasks", 0)
        total = spec.get("total_tasks", 0)
        return f"{phase} ({slug}) {completed}/{total}"

    delivery = orch.get("delivery")
    if mode == "delivery" and delivery:
        phase = delivery.get("delivery_phase", "?")
        slug = delivery.get("slug", "")
        return f"{phase} ({slug})"

    return mode


def format_context_section(stdin_data: dict) -> str:
    """Format the context usage segment from stdin data."""
    cw = stdin_data.get("context_window", {})
    window_size = cw.get("context_window_size", 0)
    usage = cw.get("current_usage", {})
    total_tokens = (
        usage.get("input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
    )

    if window_size > 0:
        pct = (total_tokens / window_size) * 100
        used_k = total_tokens / 1000
        window_k = window_size / 1000
        return f"ctx: {used_k:.1f}k/{window_k:.0f}k ({pct:.1f}%)"

    return "ctx: ?/?k"


def format_statusline(stdin_data: dict, stratus_state: dict | None) -> str:
    """Build the formatted statusline string."""
    # Git branch
    workspace = stdin_data.get("workspace", {})
    current_dir = workspace.get("current_dir", "")
    branch = _get_git_branch(current_dir)

    # Model
    model_info = stdin_data.get("model", {})
    model_name = model_info.get("display_name", "?")

    # Context
    ctx = format_context_section(stdin_data)

    # Stratus
    stratus = f"stratus: {format_stratus_section(stratus_state)}"

    # Timestamp
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")

    segments = [s for s in [branch, model_name, ctx, stratus, now] if s]
    return " | ".join(segments)


def _get_git_branch(cwd: str) -> str:
    """Read current git branch from HEAD, or return empty string."""
    if not cwd:
        return ""
    try:
        import subprocess

        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def fetch_stratus_state(api_url: str) -> dict | None:
    """GET /api/dashboard/state with 500ms timeout. Returns None on failure."""
    try:
        resp = httpx.get(f"{api_url}/api/dashboard/state", timeout=0.5)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def run() -> None:
    """Entry point: read stdin, fetch state, print output."""
    stdin_data: dict = {}
    try:
        raw = sys.stdin.read()
        if raw.strip():
            stdin_data = json.loads(raw)
    except Exception:
        pass

    port = int(os.environ.get("AI_FRAMEWORK_PORT", str(DEFAULT_PORT)))
    api_url = f"http://127.0.0.1:{port}"
    stratus_state = fetch_stratus_state(api_url)

    print(format_statusline(stdin_data, stratus_state))
