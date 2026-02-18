"""CLI command handlers for bootstrap: enhanced init and doctor."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx


def cmd_init(args: argparse.Namespace) -> None:
    """Enhanced init: detect services and write configs."""
    from stratus.bootstrap.detector import detect_services
    from stratus.bootstrap.retrieval_setup import (
        build_retrieval_config,
        detect_backends,
        merge_retrieval_into_existing,
        prompt_retrieval_setup,
        run_initial_index,
    )
    from stratus.bootstrap.writer import (
        update_ai_framework_config,
        write_ai_framework_config,
        write_project_graph,
    )
    from stratus.hooks._common import get_git_root
    from stratus.memory.database import Database
    from stratus.session.config import Config, get_data_dir

    dry_run: bool = getattr(args, "dry_run", False)
    force: bool = getattr(args, "force", False)
    skip_hooks: bool = getattr(args, "skip_hooks", False)
    skip_mcp: bool = getattr(args, "skip_mcp", False)
    skip_agents: bool = getattr(args, "skip_agents", False)
    skip_retrieval: bool = getattr(args, "skip_retrieval", False)
    enable_delivery: bool = getattr(args, "enable_delivery", False)
    scope: str | None = getattr(args, "scope", None)
    scope_explicit = scope is not None

    # Interactive mode: no --scope flag given and not dry-run
    if scope is None and not dry_run:
        scope, enable_delivery = _interactive_init()
    elif scope is None:
        scope = "local"

    # Global scope: only install hooks + MCP + statusline, skip git-dependent steps
    if scope == "global":
        from stratus.bootstrap.registration import register_hooks, register_mcp, register_statusline

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
        sl_path = register_statusline(None, dry_run=dry_run, scope="global")
        if sl_path and not dry_run:
            print(f"Statusline: {sl_path}")
        if not dry_run:
            _ensure_server()
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

    # Step 5: Detect retrieval backends
    retrieval_config = None
    interactive = not scope_explicit and not dry_run
    run_indexing = False

    if not skip_retrieval:
        backend_status = detect_backends(data_dir=str(data_dir) if not dry_run else None)
        has_any = backend_status.vexor_available or backend_status.governance_indexed
        if has_any:
            print("\nRetrieval backends:")
            if backend_status.vexor_available:
                print(f"  Vexor: available ({backend_status.vexor_version})")
            else:
                print("  Vexor: not found")
            if backend_status.governance_indexed:
                print("  Governance: indexed")
            else:
                print("  Governance: not indexed")

        ai_path = git_root / ".ai-framework.json"
        if ai_path.exists() and not force:
            # Existing project: merge retrieval config
            merged = merge_retrieval_into_existing(
                _load_json(ai_path), backend_status, str(git_root),
            )
            if not dry_run:
                update_ai_framework_config(git_root, merged)
                print(f"Config: updated retrieval in {ai_path}")
            else:
                print("[dry-run] Would update retrieval in .ai-framework.json")
        else:
            # New project or --force: build retrieval config
            if interactive and not dry_run:
                enable_vexor, enable_devrag, run_indexing = prompt_retrieval_setup(
                    backend_status, project_root=str(git_root),
                )
                retrieval_config = {
                    "vexor": {"enabled": enable_vexor, "project_root": str(git_root)},
                    "devrag": {"enabled": enable_devrag},
                }
            else:
                retrieval_config = build_retrieval_config(backend_status, str(git_root))

    # Step 6: Write .ai-framework.json
    ai_path = git_root / ".ai-framework.json"
    if not (ai_path.exists() and not force and not skip_retrieval):
        if dry_run:
            if ai_path.exists() and not force:
                print("[dry-run] .ai-framework.json exists (use --force to overwrite)")
            else:
                print(f"[dry-run] Would write .ai-framework.json to {git_root}")
        else:
            result = write_ai_framework_config(
                git_root, graph, force=force, retrieval_config=retrieval_config,
            )
            if result is None:
                print(".ai-framework.json already exists (use --force to overwrite)")
            else:
                print(f"Config: {result}")

    # Step 6b: Run initial indexing if approved
    if run_indexing and not dry_run:
        print("Running initial indexing...")
        idx_result = run_initial_index(str(git_root))
        if idx_result["status"] == "ok":
            print(f"Indexing complete: {idx_result.get('output', '')}")
        else:
            print(f"Indexing failed: {idx_result.get('message', '')}")

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

    # Step 9b: Register statusline
    from stratus.bootstrap.registration import register_statusline

    sl_path = register_statusline(git_root, dry_run=dry_run)
    if sl_path:
        if dry_run:
            print(f"[dry-run] Would register statusline at {sl_path}")
        else:
            print(f"Statusline: {sl_path}")

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

    # Step 11: Ensure HTTP server is running
    if not dry_run:
        _ensure_server()


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


def _ensure_server() -> None:
    """Start the HTTP server if not already running."""
    from stratus.hooks._common import get_api_url
    from stratus.session.config import DEFAULT_PORT

    api_url = get_api_url()

    # Check if already running
    try:
        resp = httpx.get(f"{api_url}/health", timeout=2.0)
        if resp.status_code == 200:
            print(f"Server: already running at {api_url}")
            return
    except Exception:
        pass

    # Spawn server as background daemon
    port = DEFAULT_PORT
    print(f"Starting HTTP server on port {port}...")
    subprocess.Popen(
        [sys.executable, "-m", "stratus.server.runner"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    # Wait for server to become ready
    for _ in range(10):
        time.sleep(0.5)
        try:
            resp = httpx.get(f"{api_url}/health", timeout=2.0)
            if resp.status_code == 200:
                print(f"Server: running at {api_url}")
                print(f"Dashboard: {api_url}/dashboard")
                return
        except Exception:
            continue

    print("Warning: server started but did not respond in time")


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

    # Check 5: Governance index
    gov_db = get_data_dir() / "governance.db"
    gov_ok = gov_db.exists() and gov_db.stat().st_size > 0
    _print_check(gov_ok, "Governance index")

    cwd = Path.cwd()
    for name in (".ai-framework.json", "project-graph.json"):
        exists = (cwd / name).exists()
        _print_check(exists, f"{name} in {cwd}")
        if not exists:
            all_ok = False

    if not all_ok:
        sys.exit(1)


def _load_json(path: Path) -> dict:
    """Load JSON file, return empty dict on error."""
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


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
