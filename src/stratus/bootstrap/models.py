"""Pydantic models for project bootstrap (service detection, project graph)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class ServiceType(StrEnum):
    NESTJS = "nestjs"
    NEXTJS = "nextjs"
    REACT_NATIVE = "react_native"
    PYTHON = "python"
    GO = "go"
    RUST = "rust"
    SHARED_CONTRACTS = "shared-contracts"
    GRPC_DEFINITIONS = "grpc-definitions"
    UNKNOWN = "unknown"


class ServiceInfo(BaseModel):
    name: str
    type: ServiceType
    path: str
    language: str
    entry_point: str | None = None
    package_manager: str | None = None
    dependencies: list[str] = []
    ports: dict[str, int] = {}


class SharedComponent(BaseModel):
    name: str
    type: str
    path: str
    consumers: list[str] = []


class InfraInfo(BaseModel):
    docker_compose: list[str] = []


class ProjectGraph(BaseModel):
    version: int = 1
    root: str
    detected_at: str
    services: list[ServiceInfo] = []
    shared: list[SharedComponent] = []
    infrastructure: InfraInfo = InfraInfo()
