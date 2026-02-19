"""Retrieval backend auto-detection and configuration for stratus init."""

from __future__ import annotations

import subprocess
import sys
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


def verify_cuda_runtime() -> bool:
    """Return True if onnxruntime has CUDAExecutionProvider available.

    Run this AFTER installing vexor[local-cuda] to confirm the CUDA runtime
    (libcudart.so, cuDNN) is present, not just the onnxruntime-gpu package.
    Returns False when CUDA Toolkit is missing even if onnxruntime-gpu is installed.
    """
    _probe = (
        "import onnxruntime; "
        "print('CUDA' if 'CUDAExecutionProvider' in onnxruntime.get_available_providers() else '')"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", _probe],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0 and "CUDA" in result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def install_vexor_local_package(cuda: bool) -> bool:
    """Install vexor[local-cuda] or vexor[local] into the current Python environment.

    Uses uv pip install with explicit --python so the package lands in whichever
    venv stratus runs from (pipx isolated venv or user venv). Returns True on success.
    """
    package = "vexor[local-cuda]" if cuda else "vexor[local]"
    try:
        result = subprocess.run(
            ["uv", "pip", "install", "--python", sys.executable, package],
            capture_output=True,
            timeout=300,
        )
        return result.returncode == 0
    except FileNotFoundError:
        # uv not available — fall back to pip
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package],
                capture_output=True,
                timeout=300,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    except subprocess.TimeoutExpired:
        return False


def detect_cuda() -> bool:
    """Return True if CUDA/GPU acceleration is available.

    Checks nvidia-smi first (NVIDIA driver). Falls back to probing
    onnxruntime for CUDAExecutionProvider, which covers users who have
    onnxruntime-gpu installed without nvidia-smi on PATH.
    """
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, timeout=5)
        if result.returncode == 0:
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: onnxruntime-gpu CUDAExecutionProvider check
    _ort_probe = (
        "import onnxruntime; "
        "print('CUDA' if 'CUDAExecutionProvider' in onnxruntime.get_available_providers() else '')"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", _ort_probe],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and "CUDA" in result.stdout:
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return False


def setup_vexor_local(vexor_binary: str = "vexor", *, cuda: bool | None = None) -> tuple[bool, bool]:
    """Download local embedding model and configure CPU/CUDA execution mode.

    For CUDA, tries in order per docs:
    1. `vexor local --setup --cuda` — first-time setup with CUDA
    2. `vexor local --cuda`        — mode switch (model already downloaded)
    3. Falls back to `vexor local --setup --cpu`

    Also falls back to CPU when vexor exits 0 but reports "CUDA provider not
    available" in its output (GPU present but CUDA runtime not installed).

    Returns (success, used_cuda).
    """
    if cuda is None:
        cuda = detect_cuda()

    def _run_setup(flag: str) -> tuple[bool, bool]:
        """Run vexor local --setup <flag>. Returns (exit_ok, provider_ok).

        Captures output to detect runtime availability mismatches (e.g. vexor
        exits 0 but reports 'CUDA provider not available'). Relays all output
        to the terminal so the user sees progress messages.
        """
        try:
            result = subprocess.run(
                [vexor_binary, "local", "--setup", flag],
                capture_output=True,
                text=True,
                timeout=180,
            )
            if result.stdout:
                print(result.stdout, end="", flush=True)
            if result.stderr:
                print(result.stderr, end="", flush=True, file=sys.stderr)
            cuda_unavail = "CUDA provider not available" in (result.stdout + result.stderr)
            return result.returncode == 0, not cuda_unavail
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False, False

    def _run_mode(flag: str) -> bool:
        """Switch execution mode only — model already downloaded."""
        try:
            result = subprocess.run(
                [vexor_binary, "local", flag],
                timeout=30,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    if cuda:
        exit_ok, provider_ok = _run_setup("--cuda")
        if exit_ok and provider_ok:
            return True, True
        if not exit_ok and provider_ok:
            # Setup failed for non-CUDA reasons — model may already be downloaded,
            # try mode switch. Only when provider_ok=True (no CUDA unavailable
            # warning), otherwise the mode switch would also enable broken CUDA.
            if _run_mode("--cuda"):
                return True, True
        # CUDA provider unavailable (exit 1 or "CUDA provider not available"
        # warning) — skip mode switch and fall back to CPU

    ok, _ = _run_setup("--cpu")
    return ok, False


def run_initial_index_background(
    project_root: str,
    vexor_binary: str = "vexor",
) -> bool:
    """Start vexor indexing as a detached background process. Returns True if started."""
    try:
        subprocess.Popen(
            [vexor_binary, "index", "--path", project_root],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except FileNotFoundError:
        return False


def run_initial_index(
    project_root: str,
    vexor_binary: str = "vexor",
) -> dict:
    """Run vexor index synchronously. Streams stdout to terminal. Returns status dict."""
    try:
        result = subprocess.run(
            [vexor_binary, "index", "--path", project_root],
            stderr=subprocess.PIPE,
            text=True,
            timeout=1200,
        )
    except FileNotFoundError:
        return {"status": "error", "message": "vexor binary not found"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "indexing timed out (>20 min)"}

    if result.returncode != 0:
        detail = result.stderr.strip()
        if "API key" in detail:
            return {
                "status": "api_key_missing",
                "message": "Vexor API key not configured. Run: vexor config --set-api-key <token>",
            }
        msg = f"exit code {result.returncode}" + (f": {detail}" if detail else "")
        return {"status": "error", "message": msg}

    return {"status": "ok"}
