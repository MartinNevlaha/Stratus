"""Retrieval backend auto-detection and configuration for stratus init."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class BackendStatus:
    """Result of probing retrieval backends."""

    vexor_available: bool = False
    vexor_version: str | None = None
    docker_available: bool = False
    devrag_container_exists: bool = False
    devrag_container_running: bool = False


def detect_backends(
    vexor_binary: str = "vexor",
    devrag_container: str = "devrag",
) -> BackendStatus:
    """Probe Vexor binary and Docker/DevRag availability via subprocess."""
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

    # Probe Docker
    try:
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        status.docker_available = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Probe DevRag container (only if Docker available)
    if status.docker_available:
        try:
            result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{.State.Running}}",
                    devrag_container,
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                status.devrag_container_exists = True
                status.devrag_container_running = result.stdout.strip().lower() == "true"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    return status


def build_retrieval_config(status: BackendStatus, project_root: str) -> dict:
    """Build retrieval config dict from detected backend availability."""
    return {
        "vexor": {
            "enabled": status.vexor_available,
            "project_root": project_root,
        },
        "devrag": {
            "enabled": status.devrag_container_running,
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

    # DevRag: enable if newly running, never disable
    devrag = dict(retrieval.get("devrag", {}))
    if status.devrag_container_running:
        devrag["enabled"] = True
    retrieval["devrag"] = devrag

    config["retrieval"] = retrieval
    return config


def prompt_retrieval_setup(
    status: BackendStatus,
    *,
    dry_run: bool = False,
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

    if status.devrag_container_running:
        answer = input("Enable DevRag governance search? [Y/n] ").strip().lower()
        enable_devrag = answer != "n"
    elif status.docker_available:
        if status.devrag_container_exists:
            answer = input("Start stopped DevRag container? [Y/n] ").strip().lower()
            if answer != "n":
                result = setup_devrag(container_exists=True)
                enable_devrag = result["status"] == "ok"
                if enable_devrag:
                    print("  DevRag: started")
                else:
                    print(f"  DevRag: failed to start — {result['message']}")
        else:
            answer = input("Set up DevRag governance search? [Y/n] ").strip().lower()
            if answer != "n":
                result = setup_devrag()
                enable_devrag = result["status"] == "ok"
                if enable_devrag:
                    print("  DevRag: container created and running")
                else:
                    print(f"  DevRag: setup failed — {result['message']}")

    return enable_vexor, enable_devrag, run_indexing


def setup_devrag(
    *,
    container_exists: bool = False,
    container_name: str = "devrag",
    image_name: str = "stratus-devrag",
) -> dict:
    """Build DevRag Docker image and start the container. Returns status dict."""
    try:
        if container_exists:
            result = subprocess.run(
                ["docker", "start", container_name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return {"status": "error", "message": f"start failed: {result.stderr.strip()}"}
            return {"status": "ok"}

        # Build image from bundled Dockerfile
        dockerfile = _get_devrag_dockerfile()
        from pathlib import Path

        context_dir = str(Path(dockerfile).parent)
        result = subprocess.run(
            ["docker", "build", "-t", image_name, "-f", dockerfile, context_dir],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return {"status": "error", "message": f"build failed: {result.stderr.strip()}"}

        # Run container
        result = subprocess.run(
            [
                "docker", "run", "-d",
                "--name", container_name,
                "--restart", "unless-stopped",
                "--memory", "512m",
                image_name,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return {"status": "error", "message": f"run failed: {result.stderr.strip()}"}

        return {"status": "ok"}

    except FileNotFoundError:
        return {"status": "error", "message": "docker not found"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "timeout"}


def _get_devrag_dockerfile() -> str:
    """Locate the bundled DevRag Dockerfile. Returns path as string."""
    from importlib import resources

    pkg = resources.files("stratus.bootstrap.docker")
    return str(pkg.joinpath("Dockerfile.devrag"))


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
        return {"status": "error", "message": result.stderr.strip()}

    return {"status": "ok", "output": result.stdout.strip()}
