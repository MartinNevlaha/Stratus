"""Configuration constants, config file loading, and environment overrides."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

# Context tracking thresholds (percentages of raw context)
COMPACTION_THRESHOLD_PCT = 83.5
THRESHOLD_WARN = 65
THRESHOLD_AUTOCOMPACT = 75
LEARN_THRESHOLDS = [40, 55, 65]

# Hook behavior
THROTTLE_MIN_INTERVAL_SEC = 30
CACHE_STALE_SEC = 60

# File size limits
FILE_LENGTH_WARN = 300
FILE_LENGTH_CRITICAL = 500

# Server defaults
DEFAULT_PORT = 41777
DEFAULT_DB_NAME = "memory.db"


def get_data_dir() -> Path:
    env = os.environ.get("AI_FRAMEWORK_DATA_DIR")
    if env:
        return Path(env)
    return Path.home() / ".ai-framework" / "data"


@dataclass
class Config:
    port: int = DEFAULT_PORT
    db_name: str = DEFAULT_DB_NAME

    @property
    def db_path(self) -> Path:
        return get_data_dir() / self.db_name


def load_config(path: Path | None = None) -> Config:
    """Load config from JSON file with env var overrides."""
    config = Config()

    if path and path.exists():
        try:
            data = json.loads(path.read_text())
            if "port" in data:
                config.port = data["port"]
            if "db_name" in data:
                config.db_name = data["db_name"]
        except (json.JSONDecodeError, OSError):
            pass

    # Env var overrides
    port_env = os.environ.get("AI_FRAMEWORK_PORT")
    if port_env:
        config.port = int(port_env)

    return config
