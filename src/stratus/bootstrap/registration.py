"""Hook and MCP server registration for stratus."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

from stratus.bootstrap.models import ServiceType
from stratus.orchestration.delivery_config import DeliveryConfig
from stratus.runtime_agents import (
    filter_agents,
    filter_skills,
    read_agent_template,
    read_skill_template,
)

# (event_type, matcher, module_name)
HOOK_SPECS: list[tuple[str, str, str]] = [
    ("PreToolUse", "WebSearch|WebFetch", "tool_redirect"),
    ("PostToolUse", ".*", "context_monitor"),
    ("PostToolUse", "Write|Edit", "file_checker"),
    ("PostToolUse", "Write|Edit", "tdd_enforcer"),
    ("PostToolUse", "Bash", "learning_trigger"),
    ("PreCompact", ".*", "pre_compact"),
    ("SessionStart", "compact", "post_compact_restore"),
    ("SessionEnd", ".*", "session_end"),
    ("Stop", ".*", "spec_stop_guard"),
    ("TeammateIdle", ".*", "teammate_idle"),
    ("TaskCompleted", ".*", "task_completed"),
]

_CMD_PREFIX = "uv run python -m stratus.hooks."
_MANAGED_MARKER = "<!-- managed-by: stratus"


def build_hooks_config() -> dict[str, object]:
    """Convert HOOK_SPECS into a settings.json `hooks` dict.

    Groups entries by (event_type, matcher) so multiple hooks on the same
    event+matcher are coalesced into a single group list.
    """
    # Preserve insertion order: (event_type, matcher) -> list of hook entries
    groups: dict[tuple[str, str], list[dict[str, object]]] = {}
    for event_type, matcher, module in HOOK_SPECS:
        key = (event_type, matcher)
        if key not in groups:
            groups[key] = []
        groups[key].append({"type": "command", "command": f"{_CMD_PREFIX}{module}"})

    # Collect into per-event-type lists
    events: dict[str, list[dict[str, object]]] = {}
    for (event_type, matcher), hook_entries in groups.items():
        if event_type not in events:
            events[event_type] = []
        events[event_type].append({"matcher": matcher, "hooks": hook_entries})

    return {"hooks": events}


def register_hooks(git_root: Path | None, *, dry_run: bool = False, scope: str = "local") -> Path:
    """Merge hook config into .claude/settings.json.

    Replaces the `hooks` key while preserving all other keys. Creates the
    `.claude/` directory if it does not exist. Idempotent. Returns path to
    settings.json. If dry_run is True, no files are written.

    When scope='global', writes to ~/.claude/settings.json instead of
    project-local .claude/settings.json. git_root can be None for global scope.
    """
    if scope == "global":
        dot_claude = Path.home() / ".claude"
    else:
        assert git_root is not None
        dot_claude = git_root / ".claude"
    settings_path = dot_claude / "settings.json"

    existing: dict[str, object] = {}
    if settings_path.exists():
        existing = cast(dict[str, object], json.loads(settings_path.read_text()))

    hook_config = build_hooks_config()
    merged = {**existing, **hook_config}

    if not dry_run:
        dot_claude.mkdir(parents=True, exist_ok=True)
        _ = settings_path.write_text(json.dumps(merged, indent=2))

    return settings_path


def build_statusline_config() -> dict[str, object]:
    """Return the statusLine config block for Claude Code settings."""
    return {"statusLine": {"type": "command", "command": "stratus statusline"}}


def register_statusline(
    git_root: Path | None, *, dry_run: bool = False, scope: str = "local"
) -> Path | None:
    """Merge statusLine config into .claude/settings.json.

    Non-destructive: skips if ``statusLine`` key already exists (respects
    user customization). Returns the path to settings.json, or None if
    skipped. If dry_run is True, no files are written.
    """
    if scope == "global":
        dot_claude = Path.home() / ".claude"
    else:
        assert git_root is not None
        dot_claude = git_root / ".claude"
    settings_path = dot_claude / "settings.json"

    existing: dict[str, object] = {}
    if settings_path.exists():
        existing = cast(dict[str, object], json.loads(settings_path.read_text()))

    if "statusLine" in existing:
        return None

    merged = {**existing, **build_statusline_config()}

    if not dry_run:
        dot_claude.mkdir(parents=True, exist_ok=True)
        _ = settings_path.write_text(json.dumps(merged, indent=2))

    return settings_path


def build_mcp_config(*, scope: str = "local") -> dict[str, object]:
    """Return the MCP server config block for stratus-memory."""
    entry: dict[str, object] = {
        "type": "stdio",
        "command": "uv",
        "args": ["run", "stratus", "mcp-serve"],
    }
    if scope == "local":
        entry["cwd"] = "."
    return {"mcpServers": {"stratus-memory": entry}}


def register_mcp(git_root: Path | None, *, dry_run: bool = False, scope: str = "local") -> Path:
    """Merge stratus-memory entry into .mcp.json.

    Adds or updates the `stratus-memory` server while preserving all
    other servers. Idempotent. Returns path to .mcp.json. If dry_run is
    True, no files are written.

    When scope='global', writes to ~/.claude/.mcp.json instead of
    project-local .mcp.json. git_root can be None for global scope.
    """
    if scope == "global":
        mcp_path = Path.home() / ".claude" / ".mcp.json"
    else:
        assert git_root is not None
        mcp_path = git_root / ".mcp.json"

    existing: dict[str, object] = {}
    if mcp_path.exists():
        existing = cast(dict[str, object], json.loads(mcp_path.read_text()))

    mcp_config = build_mcp_config(scope=scope)
    new_server = cast(dict[str, object], mcp_config["mcpServers"])

    existing_servers: dict[str, object] = {}
    raw = existing.get("mcpServers")
    if isinstance(raw, dict):
        existing_servers = cast(dict[str, object], raw)

    merged_servers: dict[str, object] = {**existing_servers, **new_server}
    merged: dict[str, object] = {**existing, "mcpServers": merged_servers}

    if not dry_run:
        mcp_path.parent.mkdir(parents=True, exist_ok=True)
        _ = mcp_path.write_text(json.dumps(merged, indent=2))

    return mcp_path


# ---------------------------------------------------------------------------
# Agent registration helpers
# ---------------------------------------------------------------------------


def _is_managed(file_path: Path) -> bool:
    """Return True if file_path exists and starts with the managed-by header."""
    if not file_path.exists():
        return False
    try:
        first_line = file_path.read_text(encoding="utf-8").splitlines()[0]
        return first_line.startswith(_MANAGED_MARKER)
    except (OSError, IndexError):
        return False


def _is_framework_repo(git_root: Path) -> bool:
    """Return True if git_root is the stratus framework repo itself."""
    pyproject = git_root / "pyproject.toml"
    if not pyproject.exists():
        return False
    try:
        content = pyproject.read_text(encoding="utf-8")
        return 'name = "stratus"' in content
    except OSError:
        return False


def _managed_header(content: str) -> str:
    """Build the managed-by header line including a sha256 of the content."""
    digest = hashlib.sha256(content.encode()).hexdigest()
    return f"{_MANAGED_MARKER} sha256:{digest} -->"


def register_agents(
    git_root: Path,
    config: DeliveryConfig,
    detected_types: frozenset[ServiceType],
    *,
    force: bool = False,
) -> list[str]:
    """Write runtime agent and skill files into .claude/agents/ and .claude/skills/.

    Override rules:
    - File absent            → write it
    - File has managed header → overwrite (update hash)
    - File has no header     → skip (user owns it), unless force=True

    Returns a list of file paths written, relative to git_root.
    """
    if not config.enabled:
        return []
    if _is_framework_repo(git_root):
        return []

    enabled_phases: set[str] | None = set(config.active_phases) or None

    agents_dir = git_root / ".claude" / "agents"
    skills_dir = git_root / ".claude" / "skills"

    written: list[str] = []

    # --- agents ---
    for spec in filter_agents(set(detected_types), enabled_phases=enabled_phases):
        dest = agents_dir / spec.filename
        template = read_agent_template(spec.filename)
        header = _managed_header(template)
        final_content = f"{header}\n{template}"

        if dest.exists() and not _is_managed(dest) and not force:
            continue  # user-owned, skip

        dest.parent.mkdir(parents=True, exist_ok=True)
        _ = dest.write_text(final_content, encoding="utf-8")
        written.append(dest.relative_to(git_root).as_posix())

    # --- skills ---
    for spec in filter_skills(enabled_phases=enabled_phases):
        dest = skills_dir / spec.dirname / "SKILL.md"
        template = read_skill_template(spec.dirname)
        header = _managed_header(template)
        final_content = f"{header}\n{template}"

        if dest.exists() and not _is_managed(dest) and not force:
            continue  # user-owned, skip

        dest.parent.mkdir(parents=True, exist_ok=True)
        _ = dest.write_text(final_content, encoding="utf-8")
        written.append(dest.relative_to(git_root).as_posix())

    return written
