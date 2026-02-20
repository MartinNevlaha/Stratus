"""Statusline output for Claude Code CLI — ccstatusline-compatible format."""

from __future__ import annotations

import json
import os
import sys

import httpx

from stratus.session.config import DEFAULT_PORT

# ANSI color codes
RESET = "\x1b[0m"
DIM = "\x1b[2m"
MAGENTA = "\x1b[35m"
CYAN = "\x1b[36m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
BLUE = "\x1b[34m"
BRIGHT_WHITE = "\x1b[97m"
RED = "\x1b[31m"

NBSP = "\u00a0"


def _colorize(text: str, color: str) -> str:
    """Wrap text in ANSI color codes."""
    return f"{color}{text}{RESET}"


def _format_duration(ms: int | float) -> str:
    """Convert milliseconds to human-readable duration (e.g. '1hr 23m')."""
    total_seconds = int(ms / 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    if hours > 0:
        return f"{hours}hr {minutes}m"
    return f"{minutes}m"


def format_git_segment(cwd: str) -> str | None:
    """Format git branch segment: ⎇ <branch> in magenta."""
    branch = _get_git_branch(cwd)
    if not branch:
        return None
    return _colorize(f"⎇ {branch}", MAGENTA)


def format_model_segment(stdin_data: dict) -> str | None:
    """Format model name segment in cyan."""
    model_info = stdin_data.get("model", {})
    if isinstance(model_info, str):
        name = model_info
    elif isinstance(model_info, dict):
        name = model_info.get("display_name") or model_info.get("id")
    else:
        return None
    if not name:
        return None
    return _colorize(name, CYAN)


def format_cost_segment(stdin_data: dict) -> str | None:
    """Format session cost segment: $X.XX in green."""
    cost = stdin_data.get("cost", {})
    if not isinstance(cost, dict):
        return None
    total = cost.get("total_cost_usd")
    if total is None:
        return None
    return _colorize(f"${total:.2f}", GREEN)


def format_session_segment(stdin_data: dict) -> str | None:
    """Format session duration segment: Xhr Xm in yellow."""
    cost = stdin_data.get("cost", {})
    if not isinstance(cost, dict):
        return None
    duration_ms = cost.get("total_duration_ms")
    if duration_ms is None:
        return None
    return _colorize(_format_duration(duration_ms), YELLOW)


def format_context_segment(stdin_data: dict) -> str | None:
    """Format context usage segment: Ctx: XX.X% in blue."""
    cw = stdin_data.get("context_window", {})
    window_size = cw.get("context_window_size", 0)
    usage = cw.get("current_usage", {})
    total_tokens = (
        usage.get("input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
    )
    if window_size <= 0:
        return None
    pct = (total_tokens / window_size) * 100
    return _colorize(f"Ctx: {pct:.1f}%", BLUE)


def format_stratus_segment(stratus_state: dict | None) -> str:
    """Format stratus status segment with server avatar and state indicator."""
    if stratus_state is None:
        icon = _colorize("◈", RED)
        label = _colorize("offline", DIM)
        return f"{icon} {label}"

    icon = _colorize("◈", GREEN)
    orch = stratus_state.get("orchestration", {})
    mode = orch.get("mode", "inactive")

    if mode == "inactive":
        version = stratus_state.get("version", "")
        label = "idle" + (f" v{version}" if version else "")
    elif mode == "spec":
        spec = orch.get("spec")
        if spec:
            phase = spec.get("phase", "?")
            slug = spec.get("slug", "")
            completed = spec.get("completed_tasks", 0)
            total = spec.get("total_tasks", 0)
            label = f"{phase} ({slug}) {completed}/{total}"
        else:
            label = mode
    elif mode == "delivery":
        delivery = orch.get("delivery")
        if delivery:
            phase = delivery.get("delivery_phase", "?")
            slug = delivery.get("slug", "")
            label = f"{phase} ({slug})"
        else:
            label = mode
    else:
        label = mode

    # Append active agent count if any
    agents = stratus_state.get("agents", [])
    active = [a for a in agents if isinstance(a, dict) and a.get("active")]
    if active:
        label += f" [{len(active)} agents]"

    return f"{icon} {_colorize(label, BRIGHT_WHITE)}"


def format_statusline(stdin_data: dict, stratus_state: dict | None) -> str:
    """Build the full statusline string with ANSI colors and non-breaking spaces."""
    cwd = stdin_data.get("workspace", {}).get("current_dir", "")

    segments = [
        format_git_segment(cwd),
        format_model_segment(stdin_data),
        format_cost_segment(stdin_data),
        format_session_segment(stdin_data),
        format_context_segment(stdin_data),
        format_stratus_segment(stratus_state),
    ]

    # Filter None segments, join with dim pipe separator
    sep = f" {DIM}|{RESET} "
    parts = [s for s in segments if s is not None]
    line = sep.join(parts)

    # Replace spaces with non-breaking spaces (prevent terminal trimming)
    line = line.replace(" ", NBSP)

    # Prefix with ANSI reset to override Claude Code's dim styling
    return f"{RESET}{line}"


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
