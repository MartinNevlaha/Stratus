"""Configuration for Vexor, DevRag, and the unified retrieval layer."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VexorConfig:
    enabled: bool = True
    binary_path: str = "vexor"
    model: str = "nomic-embed-text-v1.5"
    exclude_patterns: list[str] = field(default_factory=list)


@dataclass
class DevRagConfig:
    enabled: bool = True
    container_name: str = "devrag"
    fallback_to_flat_files: bool = False


@dataclass
class RetrievalConfig:
    vexor: VexorConfig = field(default_factory=VexorConfig)
    devrag: DevRagConfig = field(default_factory=DevRagConfig)
    project_root: str | None = None


def load_retrieval_config(path: Path | None = None) -> RetrievalConfig:
    """Load retrieval config from JSON file with env var overrides."""
    config = RetrievalConfig()

    if path and path.exists():
        try:
            text = path.read_text()
            if text.strip():
                data = json.loads(text)
                retrieval = data.get("retrieval", {})
                _apply_vexor(config.vexor, retrieval.get("vexor", {}))
                _apply_devrag(config.devrag, retrieval.get("devrag", {}))
                if "project_root" in retrieval:
                    config.project_root = retrieval["project_root"]
        except (json.JSONDecodeError, OSError):
            pass

    # Env var overrides
    vexor_path = os.environ.get("AI_FRAMEWORK_VEXOR_PATH")
    if vexor_path:
        config.vexor.binary_path = vexor_path

    devrag_container = os.environ.get("AI_FRAMEWORK_DEVRAG_CONTAINER")
    if devrag_container:
        config.devrag.container_name = devrag_container

    return config


def _apply_vexor(cfg: VexorConfig, data: dict) -> None:
    if "enabled" in data:
        cfg.enabled = data["enabled"]
    if "binary_path" in data:
        cfg.binary_path = data["binary_path"]
    if "model" in data:
        cfg.model = data["model"]
    if "exclude_patterns" in data:
        cfg.exclude_patterns = data["exclude_patterns"]


def _apply_devrag(cfg: DevRagConfig, data: dict) -> None:
    if "enabled" in data:
        cfg.enabled = data["enabled"]
    if "container_name" in data:
        cfg.container_name = data["container_name"]
    if "fallback_to_flat_files" in data:
        cfg.fallback_to_flat_files = data["fallback_to_flat_files"]
