"""Tests for bootstrap service detector."""

from __future__ import annotations

import json
from pathlib import Path

from stratus.bootstrap.detector import detect_services
from stratus.bootstrap.models import ServiceType


def _write(path: Path, content: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


class TestDetectServices:
    def test_empty_dir_returns_single_unknown_service(self, tmp_path):
        graph = detect_services(tmp_path)
        assert graph.root == str(tmp_path)
        assert len(graph.services) == 1
        assert graph.services[0].type == ServiceType.UNKNOWN

    def test_detects_nestjs(self, tmp_path):
        svc_dir = tmp_path / "apps" / "api"
        _write(
            svc_dir / "package.json",
            json.dumps({"name": "api", "dependencies": {"@nestjs/core": "^10"}}),
        )
        _write(svc_dir / "nest-cli.json", "{}")
        graph = detect_services(tmp_path)
        nestjs_svcs = [s for s in graph.services if s.type == ServiceType.NESTJS]
        assert len(nestjs_svcs) == 1
        assert nestjs_svcs[0].name == "api"
        assert nestjs_svcs[0].language == "typescript"

    def test_detects_nextjs(self, tmp_path):
        svc_dir = tmp_path / "apps" / "web"
        _write(svc_dir / "package.json", json.dumps({"name": "web"}))
        _write(svc_dir / "next.config.js", "module.exports = {}")
        graph = detect_services(tmp_path)
        nextjs_svcs = [s for s in graph.services if s.type == ServiceType.NEXTJS]
        assert len(nextjs_svcs) == 1
        assert nextjs_svcs[0].language == "typescript"

    def test_detects_react_native(self, tmp_path):
        svc_dir = tmp_path / "apps" / "mobile"
        _write(
            svc_dir / "package.json",
            json.dumps({"name": "mobile", "dependencies": {"expo": "~50"}}),
        )
        graph = detect_services(tmp_path)
        rn_svcs = [s for s in graph.services if s.type == ServiceType.REACT_NATIVE]
        assert len(rn_svcs) == 1

    def test_detects_python(self, tmp_path):
        svc_dir = tmp_path / "services" / "ml"
        _write(svc_dir / "pyproject.toml", "[project]\nname = 'ml'")
        _write(svc_dir / "main.py", "")
        graph = detect_services(tmp_path)
        py_svcs = [s for s in graph.services if s.type == ServiceType.PYTHON]
        assert len(py_svcs) == 1
        assert py_svcs[0].language == "python"

    def test_detects_go(self, tmp_path):
        svc_dir = tmp_path / "services" / "worker"
        _write(svc_dir / "go.mod", "module example.com/worker\n\ngo 1.21")
        graph = detect_services(tmp_path)
        go_svcs = [s for s in graph.services if s.type == ServiceType.GO]
        assert len(go_svcs) == 1
        assert go_svcs[0].language == "go"

    def test_detects_rust(self, tmp_path):
        svc_dir = tmp_path / "services" / "engine"
        _write(svc_dir / "Cargo.toml", '[package]\nname = "engine"')
        _write(svc_dir / "src" / "main.rs", "fn main() {}")
        graph = detect_services(tmp_path)
        rust_svcs = [s for s in graph.services if s.type == ServiceType.RUST]
        assert len(rust_svcs) == 1
        assert rust_svcs[0].language == "rust"

    def test_detects_shared_contracts(self, tmp_path):
        sc_dir = tmp_path / "schemas"
        _write(sc_dir / "user.ts", "export interface User {}")
        _write(sc_dir / "order.json", "{}")
        graph = detect_services(tmp_path)
        shared = [s for s in graph.shared if s.type == "shared-contracts"]
        assert len(shared) == 1

    def test_detects_proto_dir(self, tmp_path):
        proto_dir = tmp_path / "proto"
        _write(proto_dir / "user.proto", 'syntax = "proto3";')
        graph = detect_services(tmp_path)
        grpc = [s for s in graph.shared if s.type == "grpc-definitions"]
        assert len(grpc) == 1

    def test_skips_node_modules(self, tmp_path):
        nm_dir = tmp_path / "node_modules" / "some-pkg"
        _write(nm_dir / "package.json", json.dumps({"name": "some-pkg"}))
        _write(nm_dir / "nest-cli.json", "{}")
        graph = detect_services(tmp_path)
        nestjs_svcs = [s for s in graph.services if s.type == ServiceType.NESTJS]
        assert len(nestjs_svcs) == 0

    def test_skips_dot_git(self, tmp_path):
        git_dir = tmp_path / ".git" / "modules" / "sub"
        _write(git_dir / "go.mod", "module sub\n\ngo 1.21")
        graph = detect_services(tmp_path)
        go_svcs = [s for s in graph.services if s.type == ServiceType.GO]
        assert len(go_svcs) == 0

    def test_mixed_monorepo(self, tmp_path):
        api_dir = tmp_path / "apps" / "api"
        _write(
            api_dir / "package.json",
            json.dumps({"name": "api", "dependencies": {"@nestjs/core": "^10"}}),
        )
        _write(api_dir / "nest-cli.json", "{}")

        web_dir = tmp_path / "apps" / "web"
        _write(web_dir / "package.json", json.dumps({"name": "web"}))
        _write(web_dir / "next.config.js", "")

        ml_dir = tmp_path / "services" / "ml"
        _write(ml_dir / "pyproject.toml", "[project]\nname = 'ml'")
        _write(ml_dir / "main.py", "")

        graph = detect_services(tmp_path)
        types = {s.type for s in graph.services}
        assert ServiceType.NESTJS in types
        assert ServiceType.NEXTJS in types
        assert ServiceType.PYTHON in types

    def test_graph_has_detected_at(self, tmp_path):
        graph = detect_services(tmp_path)
        assert graph.detected_at != ""

    def test_detects_kotlin_gradle_kts(self, tmp_path):
        svc_dir = tmp_path / "services" / "payment"
        _write(svc_dir / "build.gradle.kts", 'plugins { kotlin("jvm") }')
        _write(svc_dir / "src" / "main" / "kotlin" / "App.kt", "fun main() {}")
        graph = detect_services(tmp_path)
        kotlin_svcs = [s for s in graph.services if s.type == ServiceType.KOTLIN]
        assert len(kotlin_svcs) == 1
        assert kotlin_svcs[0].language == "kotlin"
        assert kotlin_svcs[0].package_manager == "gradle"

    def test_detects_kotlin_gradle_groovy(self, tmp_path):
        svc_dir = tmp_path / "services" / "auth"
        _write(svc_dir / "build.gradle", "apply plugin: 'kotlin'")
        _write(svc_dir / "src" / "main" / "kotlin" / "Main.kt", "fun main() {}")
        graph = detect_services(tmp_path)
        kotlin_svcs = [s for s in graph.services if s.type == ServiceType.KOTLIN]
        assert len(kotlin_svcs) == 1

    def test_detects_fastapi(self, tmp_path):
        svc_dir = tmp_path / "services" / "api"
        _write(svc_dir / "pyproject.toml", "[project]\nname = 'api'\ndependencies = ['fastapi']")
        _write(svc_dir / "main.py", "from fastapi import FastAPI")
        graph = detect_services(tmp_path)
        fastapi_svcs = [s for s in graph.services if s.type == ServiceType.FASTAPI]
        assert len(fastapi_svcs) == 1
        assert fastapi_svcs[0].language == "python"

    def test_detects_fastapi_from_requirements(self, tmp_path):
        svc_dir = tmp_path / "services" / "api"
        _write(svc_dir / "requirements.txt", "fastapi>=0.100\nuvicorn")
        _write(svc_dir / "main.py", "from fastapi import FastAPI")
        graph = detect_services(tmp_path)
        fastapi_svcs = [s for s in graph.services if s.type == ServiceType.FASTAPI]
        assert len(fastapi_svcs) == 1

    def test_detects_django(self, tmp_path):
        svc_dir = tmp_path / "services" / "web"
        _write(svc_dir / "manage.py", "#!/usr/bin/env python")
        _write(svc_dir / "requirements.txt", "django>=4.2")
        graph = detect_services(tmp_path)
        django_svcs = [s for s in graph.services if s.type == ServiceType.DJANGO]
        assert len(django_svcs) == 1
        assert django_svcs[0].language == "python"
        assert django_svcs[0].entry_point == "manage.py"

    def test_detects_django_without_requirements(self, tmp_path):
        svc_dir = tmp_path / "services" / "cms"
        _write(svc_dir / "manage.py", "#!/usr/bin/env python")
        graph = detect_services(tmp_path)
        django_svcs = [s for s in graph.services if s.type == ServiceType.DJANGO]
        assert len(django_svcs) == 1

    def test_relative_paths(self, tmp_path):
        svc_dir = tmp_path / "apps" / "api"
        _write(
            svc_dir / "package.json",
            json.dumps({"name": "api", "dependencies": {"@nestjs/core": "^10"}}),
        )
        _write(svc_dir / "nest-cli.json", "{}")
        graph = detect_services(tmp_path)
        nestjs = [s for s in graph.services if s.type == ServiceType.NESTJS][0]
        # Path should be relative (not absolute)
        assert not nestjs.path.startswith("/")
