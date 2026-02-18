"""Tests for bootstrap Pydantic models."""

from __future__ import annotations

import json

from stratus.bootstrap.models import (
    InfraInfo,
    ProjectGraph,
    ServiceInfo,
    ServiceType,
    SharedComponent,
)


class TestServiceType:
    def test_all_values_present(self):
        values = {e.value for e in ServiceType}
        assert "nestjs" in values
        assert "nextjs" in values
        assert "react_native" in values
        assert "python" in values
        assert "go" in values
        assert "rust" in values
        assert "shared-contracts" in values
        assert "grpc-definitions" in values
        assert "unknown" in values

    def test_is_str_enum(self):
        assert ServiceType.NESTJS == "nestjs"
        assert ServiceType.PYTHON == "python"


class TestServiceInfo:
    def test_minimal_creation(self):
        svc = ServiceInfo(
            name="api", type=ServiceType.NESTJS, path="apps/api", language="typescript"
        )
        assert svc.name == "api"
        assert svc.type == ServiceType.NESTJS
        assert svc.path == "apps/api"
        assert svc.language == "typescript"
        assert svc.entry_point is None
        assert svc.package_manager is None
        assert svc.dependencies == []
        assert svc.ports == {}

    def test_full_creation(self):
        svc = ServiceInfo(
            name="api",
            type=ServiceType.NESTJS,
            path="apps/api",
            language="typescript",
            entry_point="src/main.ts",
            package_manager="pnpm",
            dependencies=["@nestjs/core"],
            ports={"http": 3000},
        )
        assert svc.entry_point == "src/main.ts"
        assert svc.package_manager == "pnpm"
        assert svc.dependencies == ["@nestjs/core"]
        assert svc.ports == {"http": 3000}

    def test_json_round_trip(self):
        svc = ServiceInfo(
            name="web", type=ServiceType.NEXTJS, path="apps/web", language="typescript"
        )
        data = json.loads(svc.model_dump_json())
        svc2 = ServiceInfo(**data)
        assert svc2.name == svc.name
        assert svc2.type == svc.type


class TestSharedComponent:
    def test_creation(self):
        sc = SharedComponent(name="schemas", type="shared-contracts", path="packages/schemas")
        assert sc.name == "schemas"
        assert sc.consumers == []

    def test_with_consumers(self):
        sc = SharedComponent(
            name="proto", type="grpc-definitions", path="proto", consumers=["api", "worker"]
        )
        assert sc.consumers == ["api", "worker"]


class TestInfraInfo:
    def test_defaults(self):
        infra = InfraInfo()
        assert infra.docker_compose == []

    def test_with_files(self):
        infra = InfraInfo(docker_compose=["docker-compose.yml", "docker-compose.dev.yml"])
        assert len(infra.docker_compose) == 2


class TestProjectGraph:
    def test_creation(self):
        graph = ProjectGraph(root="/repo", detected_at="2026-01-01T00:00:00Z")
        assert graph.version == 1
        assert graph.root == "/repo"
        assert graph.services == []
        assert graph.shared == []

    def test_with_services(self):
        svc = ServiceInfo(
            name="api", type=ServiceType.NESTJS, path="apps/api", language="typescript"
        )
        graph = ProjectGraph(
            root="/repo",
            detected_at="2026-01-01T00:00:00Z",
            services=[svc],
        )
        assert len(graph.services) == 1
        assert graph.services[0].name == "api"

    def test_json_round_trip(self):
        svc = ServiceInfo(
            name="api", type=ServiceType.NESTJS, path="apps/api", language="typescript"
        )
        graph = ProjectGraph(root="/repo", detected_at="2026-01-01T00:00:00Z", services=[svc])
        data = json.loads(graph.model_dump_json())
        graph2 = ProjectGraph(**data)
        assert graph2.root == graph.root
        assert len(graph2.services) == 1
        assert graph2.services[0].name == "api"
