"""Uvicorn launcher with port management and port.lock file."""

from __future__ import annotations

import json
import os
import signal
from pathlib import Path

from stratus.session.config import Config, get_data_dir, load_config


def get_port_lock_path() -> Path:
    return get_data_dir() / "port.lock"


def write_port_lock(port: int) -> Path:
    lock_path = get_port_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps({"port": port, "pid": os.getpid()}))
    return lock_path


def read_port_lock() -> dict:
    lock_path = get_port_lock_path()
    try:
        return json.loads(lock_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def remove_port_lock() -> None:
    lock_path = get_port_lock_path()
    lock_path.unlink(missing_ok=True)


def run_server(config: Config | None = None) -> None:
    """Start the HTTP API server with uvicorn."""
    import uvicorn

    if config is None:
        config = load_config()

    config.db_path.parent.mkdir(parents=True, exist_ok=True)

    write_port_lock(config.port)

    def cleanup(signum, frame):
        remove_port_lock()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    try:
        uvicorn.run(
            "stratus.server.app:create_app",
            factory=True,
            host="127.0.0.1",
            port=config.port,
        )
    finally:
        remove_port_lock()
