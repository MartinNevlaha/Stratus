"""CLI command handlers for bootstrap: enhanced init and doctor."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import httpx


def cmd_init(args: argparse.Namespace) -> None:
    """Enhanced init: detect services and write configs."""
    from stratus.bootstrap.detector import detect_services
    from stratus.bootstrap.writer import write_ai_framework_config, write_project_graph
    from stratus.hooks._common import get_git_root
    from stratus.memory.database import Database
    from stratus.session.config import Config, get_data_dir

    dry_run: bool = getattr(args, "dry_run", False)
    force: bool = getattr(args, "force", False)
    skip_hooks: bool = getattr(args, "skip_hooks", False)
    skip_mcp: bool = getattr(args, "skip_mcp", False)
    skip_agents: bool = getattr(args, "skip_agents", False)
    enable_delivery: bool = getattr(args, "enable_delivery", False)
    scope: str | None = getattr(args, "scope", None)

    # Interactive mode: no --scope flag given and not dry-run
    if scope is None and not dry_run:
        scope, enable_delivery = _interactive_init()
    elif scope is None:
        scope = "local"

    # Global scope: only install hooks + MCP, skip git-dependent steps
    if scope == "global":
        from stratus.bootstrap.registration import register_hooks, register_mcp

        if not skip_hooks:
            hooks_path = register_hooks(None, dry_run=dry_run, scope="global")
            if dry_run:
                print(f"[dry-run] Would register hooks at {hooks_path}")
            else:
                print(f"Hooks: {hooks_path}")
        if not skip_mcp:
            mcp_path = register_mcp(None, dry_run=dry_run, scope="global")
            if dry_run:
                print(f"[dry-run] Would register MCP at {mcp_path}")
            else:
                print(f"MCP: {mcp_path}")
        print("\nGlobal installation complete (hooks and MCP registered in ~/.claude/)")
        return

    # Step 1: Detect git root
    git_root = get_git_root()
    if git_root is None:
        print("Error: not in a git repository", file=sys.stderr)
        sys.exit(1)

    # Step 2: Create data dir + memory DB
    data_dir = get_data_dir()
    if dry_run:
        print(f"[dry-run] Would create data directory: {data_dir}")
    else:
        data_dir.mkdir(parents=True, exist_ok=True)
        config = Config()
        db = Database(str(config.db_path))
        db.close()
        print(f"Data directory: {data_dir}")

    # Step 3: Detect services
    graph = detect_services(git_root)

    # Step 4: Write project-graph.json
    if dry_run:
        print(f"[dry-run] Would write project-graph.json to {git_root}")
    else:
        pg_path = write_project_graph(graph, git_root)
        print(f"Project graph: {pg_path}")

    # Step 5: Write .ai-framework.json
    if dry_run:
        ai_path = git_root / ".ai-framework.json"
        if ai_path.exists() and not force:
            print("[dry-run] .ai-framework.json exists (use --force to overwrite)")
        else:
            print(f"[dry-run] Would write .ai-framework.json to {git_root}")
    else:
        result = write_ai_framework_config(git_root, graph, force=force)
        if result is None:
            print(".ai-framework.json already exists (use --force to overwrite)")
        else:
            print(f"Config: {result}")

    # Step 6: Print summary
    print(f"\nDetected {len(graph.services)} service(s):")
    for svc in graph.services:
        print(f"  - {svc.name} ({svc.type}, {svc.language}) at {svc.path}")
    if graph.shared:
        print(f"Detected {len(graph.shared)} shared component(s):")
        for sc in graph.shared:
            print(f"  - {sc.name} ({sc.type}) at {sc.path}")

    # Step 8: Register hooks
    if not skip_hooks:
        from stratus.bootstrap.registration import register_hooks

        hooks_path = register_hooks(git_root, dry_run=dry_run)
        if dry_run:
            print(f"[dry-run] Would register hooks at {hooks_path}")
        else:
            print(f"Hooks: {hooks_path}")

    # Step 9: Register MCP server
    if not skip_mcp:
        from stratus.bootstrap.registration import register_mcp

        mcp_path = register_mcp(git_root, dry_run=dry_run)
        if dry_run:
            print(f"[dry-run] Would register MCP at {mcp_path}")
        else:
            print(f"MCP: {mcp_path}")

    # Step 10: Register delivery agents (gated)
    if not skip_agents:
        from stratus.bootstrap.registration import register_agents
        from stratus.orchestration.delivery_config import load_delivery_config
        from stratus.runtime_agents import get_detected_types

        ai_fw_path = git_root / ".ai-framework.json"
        delivery_config = load_delivery_config(ai_fw_path)

        # --enable-delivery flag forces enabled=True
        if enable_delivery:
            delivery_config.enabled = True

        if delivery_config.enabled:
            detected_types = frozenset(get_detected_types(graph.model_dump()))
            written = register_agents(git_root, delivery_config, detected_types, force=force)
            print(f"Agents: {len(written)} agent(s) installed")


def _interactive_init() -> tuple[str, bool]:
    """Prompt user for init options. Returns (scope, enable_delivery)."""
    print("Choose installation scope:")
    print("  1) Project — hooks and MCP in the current project (needs git repo)")
    print("  2) Global  — hooks and MCP in ~/.claude/ (works across all projects)")
    choice = input("Scope [1/2] (default: 1): ").strip()
    scope = "global" if choice == "2" else "local"

    enable_delivery = False
    if scope == "local":
        answer = input("Install delivery agents and skills? [y/N] ").strip()
        enable_delivery = answer.lower().startswith("y")

    print()
    return scope, enable_delivery


def cmd_doctor(_args: argparse.Namespace) -> None:
    """Run health checks on all stratus components."""
    from stratus.session.config import Config, get_data_dir

    all_ok = True

    # Check 1: Memory DB
    _ = get_data_dir()
    config = Config()
    db_path = config.db_path
    if db_path.exists():
        _print_check(True, f"Memory DB exists ({db_path})")
    else:
        _print_check(False, f"Memory DB not found ({db_path})")
        all_ok = False

    # Check 2: HTTP server health
    try:
        from stratus.hooks._common import get_api_url

        api_url = get_api_url()
        resp = httpx.get(f"{api_url}/health", timeout=2.0)
        if resp.status_code == 200:
            _print_check(True, "HTTP server responding")
        else:
            _print_check(False, f"HTTP server returned {resp.status_code}")
            all_ok = False
    except Exception:
        _print_check(False, "HTTP server not reachable")
        all_ok = False

    # Check 3: MCP server binary
    mcp_available = _check_cmd(["stratus", "mcp-serve", "--help"])
    _print_check(mcp_available, "MCP server binary")

    # Check 4: Vexor
    vexor_ok = _check_cmd(["vexor", "--version"])
    _print_check(vexor_ok, "Vexor binary")

    # Check 5: DevRag (Docker container)
    devrag_ok = _check_cmd(["docker", "ps", "--filter", "name=devrag", "--format", "{{.Names}}"])
    _print_check(devrag_ok, "DevRag (Docker)")

    # Check 6: .ai-framework.json
    cwd = Path.cwd()
    ai_config = cwd / ".ai-framework.json"
    _print_check(ai_config.exists(), f".ai-framework.json in {cwd}")
    if not ai_config.exists():
        all_ok = False

    # Check 7: project-graph.json
    pg = cwd / "project-graph.json"
    _print_check(pg.exists(), f"project-graph.json in {cwd}")
    if not pg.exists():
        all_ok = False

    if not all_ok:
        sys.exit(1)


def _print_check(ok: bool, label: str) -> None:
    """Print a health check result line."""
    mark = "OK" if ok else "FAIL"
    print(f"  [{mark}] {label}")


def _check_cmd(cmd: list[str]) -> bool:
    """Run a command and return True if exit code is 0."""
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
