"""Retrieval backend auto-detection and configuration for stratus init."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BackendStatus:
    """Result of probing retrieval backends."""

    vexor_available: bool = False
    vexor_version: str | None = None
    governance_indexed: bool = False


def detect_backends(
    vexor_binary: str = "vexor",
    data_dir: str | None = None,
) -> BackendStatus:
    """Probe Vexor binary availability and check if governance.db exists."""
    status = BackendStatus()

    # Probe Vexor
    try:
        result = subprocess.run(
            [vexor_binary, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            status.vexor_available = True
            status.vexor_version = result.stdout.strip() or None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Check if governance.db exists
    if data_dir:
        gov_db = Path(data_dir) / "governance.db"
        if gov_db.exists() and gov_db.stat().st_size > 0:
            status.governance_indexed = True

    return status


def build_retrieval_config(status: BackendStatus, project_root: str) -> dict:
    """Build retrieval config dict from detected backend availability."""
    return {
        "vexor": {
            "enabled": status.vexor_available,
            "project_root": project_root,
        },
        "devrag": {
            "enabled": status.governance_indexed,
        },
    }


def merge_retrieval_into_existing(
    existing_config: dict,
    status: BackendStatus,
    project_root: str,
) -> dict:
    """Merge retrieval settings into existing config. Only enable, never downgrade."""
    config = {k: v for k, v in existing_config.items()}
    retrieval = dict(config.get("retrieval", {}))

    # Vexor: enable if newly available, never disable
    vexor = dict(retrieval.get("vexor", {}))
    if status.vexor_available:
        vexor["enabled"] = True
    vexor["project_root"] = project_root
    retrieval["vexor"] = vexor

    # DevRag/Governance: enable if newly indexed, never disable
    devrag = dict(retrieval.get("devrag", {}))
    if status.governance_indexed:
        devrag["enabled"] = True
    retrieval["devrag"] = devrag

    config["retrieval"] = retrieval
    return config


def prompt_retrieval_setup(
    status: BackendStatus,
    *,
    dry_run: bool = False,
    project_root: str | None = None,
) -> tuple[bool, bool, bool]:
    """Interactive prompts for retrieval setup.

    Returns (enable_vexor, enable_devrag, run_indexing).
    """
    if dry_run:
        return False, False, False

    enable_vexor = False
    enable_devrag = False
    run_indexing = False

    if status.vexor_available:
        answer = input("Enable Vexor code search? [Y/n] ").strip().lower()
        enable_vexor = answer != "n"
        if enable_vexor:
            idx_answer = input("Run initial indexing now? [Y/n] ").strip().lower()
            run_indexing = idx_answer != "n"

    prompt = "Index governance docs (.claude/rules, docs/decisions, etc.)? [Y/n] "
    gov_answer = input(prompt).strip().lower()
    enable_devrag = gov_answer != "n"

    return enable_vexor, enable_devrag, run_indexing


def run_governance_index(project_root: str, db_path: str) -> dict:
    """Create GovernanceStore, index project, return stats."""
    from stratus.retrieval.governance_store import GovernanceStore

    try:
        store = GovernanceStore(db_path)
        stats = store.index_project(project_root)
        store.close()
        return {"status": "ok", **stats}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def configure_vexor_api_key(api_key: str, vexor_binary: str = "vexor") -> bool:
    """Run `vexor config --set-api-key <key>`. Returns True on success."""
    try:
        result = subprocess.run(
            [vexor_binary, "config", "--set-api-key", api_key],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def setup_vexor_local(vexor_binary: str = "vexor") -> bool:
    """Run `vexor local --setup` to download local embedding model. Returns True on success."""
    try:
        result = subprocess.run(
            [vexor_binary, "local", "--setup"],
            timeout=180,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def run_initial_index(
    project_root: str,
    vexor_binary: str = "vexor",
) -> dict:
    """Run vexor index via subprocess. Returns status dict."""
    try:
        result = subprocess.run(
            [vexor_binary, "index", "--path", project_root],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        return {"status": "error", "message": "vexor binary not found"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "indexing timeout"}

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        if "API key" in detail:
            return {
                "status": "api_key_missing",
                "message": "Vexor API key not configured. Run: vexor config --set-api-key <token>",
            }
        msg = f"exit code {result.returncode}" + (f": {detail}" if detail else "")
        return {"status": "error", "message": msg}

    return {"status": "ok", "output": result.stdout.strip()}
