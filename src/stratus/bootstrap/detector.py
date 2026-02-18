"""Service detection heuristics for project bootstrap."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from stratus.bootstrap.models import (
    InfraInfo,
    ProjectGraph,
    ServiceInfo,
    ServiceType,
    SharedComponent,
)

SKIP_DIRS = {
    "node_modules",
    ".git",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
    "coverage",
}


def detect_services(repo_root: Path) -> ProjectGraph:
    """Scan repo_root up to depth 2, detect service boundaries."""
    services: list[ServiceInfo] = []
    shared: list[SharedComponent] = []
    docker_compose_files: list[str] = []

    candidates: list[Path] = []
    for entry in sorted(repo_root.iterdir()):
        if entry.name in SKIP_DIRS or entry.name.startswith("."):
            continue
        if entry.is_file() and entry.name.startswith("docker-compose"):
            docker_compose_files.append(entry.name)
            continue
        if not entry.is_dir():
            continue
        candidates.append(entry)
        # depth 2
        for sub in sorted(entry.iterdir()):
            if sub.is_dir() and sub.name not in SKIP_DIRS and not sub.name.startswith("."):
                candidates.append(sub)

    for candidate in candidates:
        result = _classify_dir(candidate, repo_root)
        if result is None:
            continue
        if isinstance(result, ServiceInfo):
            services.append(result)
        elif isinstance(result, SharedComponent):
            shared.append(result)

    if not services:
        services.append(
            ServiceInfo(
                name=repo_root.name,
                type=ServiceType.UNKNOWN,
                path=".",
                language="unknown",
            )
        )

    return ProjectGraph(
        root=str(repo_root),
        detected_at=datetime.now(UTC).isoformat(),
        services=services,
        shared=shared,
        infrastructure=InfraInfo(docker_compose=docker_compose_files),
    )


def _classify_dir(d: Path, repo_root: Path) -> ServiceInfo | SharedComponent | None:
    """Apply heuristics to classify a directory as a service or shared component."""
    rel_path = str(d.relative_to(repo_root))
    name = d.name

    # Shared: dir named "schemas" with .ts/.json files
    if name == "schemas":
        ts_or_json = list(d.glob("*.ts")) + list(d.glob("*.json"))
        if ts_or_json:
            return SharedComponent(name=name, type="shared-contracts", path=rel_path)

    # Shared: dir named "proto" with .proto files
    if name == "proto":
        protos = list(d.glob("*.proto"))
        if protos:
            return SharedComponent(name=name, type="grpc-definitions", path=rel_path)

    pkg_json = d / "package.json"
    nest_cli = d / "nest-cli.json"

    # NestJS: package.json + nest-cli.json
    if pkg_json.exists() and nest_cli.exists():
        pkg_data = _read_json(pkg_json)
        pkg_name = pkg_data.get("name", name) if pkg_data else name
        return ServiceInfo(
            name=pkg_name,
            type=ServiceType.NESTJS,
            path=rel_path,
            language="typescript",
            entry_point="src/main.ts",
            package_manager=_detect_pm(d),
            dependencies=list((pkg_data or {}).get("dependencies", {}).keys()),
        )

    # Next.js: package.json + next.config.*
    if pkg_json.exists():
        next_configs = list(d.glob("next.config.*"))
        if next_configs:
            pkg_data = _read_json(pkg_json)
            pkg_name = pkg_data.get("name", name) if pkg_data else name
            return ServiceInfo(
                name=pkg_name,
                type=ServiceType.NEXTJS,
                path=rel_path,
                language="typescript",
                entry_point="src/app/page.tsx",
                package_manager=_detect_pm(d),
                dependencies=list((pkg_data or {}).get("dependencies", {}).keys()),
            )

    # React Native: package.json + expo in deps
    if pkg_json.exists():
        pkg_data = _read_json(pkg_json)
        if pkg_data:
            all_deps = {
                **pkg_data.get("dependencies", {}),
                **pkg_data.get("devDependencies", {}),
            }
            if "expo" in all_deps:
                pkg_name = pkg_data.get("name", name)
                return ServiceInfo(
                    name=pkg_name,
                    type=ServiceType.REACT_NATIVE,
                    path=rel_path,
                    language="typescript",
                    package_manager=_detect_pm(d),
                    dependencies=list(pkg_data.get("dependencies", {}).keys()),
                )

    # Python: pyproject.toml + main.py or app.py
    pyproject = d / "pyproject.toml"
    if pyproject.exists() and ((d / "main.py").exists() or (d / "app.py").exists()):
        entry = "main.py" if (d / "main.py").exists() else "app.py"
        return ServiceInfo(
            name=name,
            type=ServiceType.PYTHON,
            path=rel_path,
            language="python",
            entry_point=entry,
            package_manager="uv",
        )

    # Go: go.mod
    go_mod = d / "go.mod"
    if go_mod.exists():
        return ServiceInfo(
            name=name,
            type=ServiceType.GO,
            path=rel_path,
            language="go",
            entry_point="main.go",
            package_manager="go",
        )

    # Rust: Cargo.toml + src/main.rs
    cargo = d / "Cargo.toml"
    if cargo.exists() and (d / "src" / "main.rs").exists():
        return ServiceInfo(
            name=name,
            type=ServiceType.RUST,
            path=rel_path,
            language="rust",
            entry_point="src/main.rs",
            package_manager="cargo",
        )

    return None


def _read_json(path: Path) -> dict | None:  # type: ignore[type-arg]
    try:
        return json.loads(path.read_text())  # type: ignore[no-any-return]
    except Exception:
        return None


def _detect_pm(d: Path) -> str:
    if (d / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (d / "yarn.lock").exists():
        return "yarn"
    if (d / "bun.lockb").exists():
        return "bun"
    return "npm"
