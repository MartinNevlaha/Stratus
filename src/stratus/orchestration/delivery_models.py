"""Pydantic models and enums for the delivery orchestration layer."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class DeliveryPhase(StrEnum):
    DISCOVERY = "discovery"
    ARCHITECTURE = "architecture"
    PLANNING = "planning"
    IMPLEMENTATION = "implementation"
    QA = "qa"
    GOVERNANCE = "governance"
    PERFORMANCE = "performance"
    RELEASE = "release"
    LEARNING = "learning"


class OrchestrationMode(StrEnum):
    CLASSIC = "classic"
    SWARM = "swarm"
    AUTO = "auto"


# Default active phases per mode
DEFAULT_ACTIVE_PHASES: dict[OrchestrationMode, list[DeliveryPhase]] = {
    OrchestrationMode.CLASSIC: [
        DeliveryPhase.IMPLEMENTATION,
        DeliveryPhase.QA,
        DeliveryPhase.GOVERNANCE,
        DeliveryPhase.RELEASE,
        DeliveryPhase.LEARNING,
    ],
    OrchestrationMode.SWARM: list(DeliveryPhase),  # All 9
    OrchestrationMode.AUTO: [
        DeliveryPhase.IMPLEMENTATION,
        DeliveryPhase.QA,
        DeliveryPhase.GOVERNANCE,
        DeliveryPhase.RELEASE,
        DeliveryPhase.LEARNING,
    ],
}


def get_default_phases(mode: OrchestrationMode | str) -> list[DeliveryPhase]:
    """Get default active phases for an orchestration mode."""
    if not isinstance(mode, OrchestrationMode):
        mode = OrchestrationMode(mode)
    return list(DEFAULT_ACTIVE_PHASES[mode])


class PhaseResult(BaseModel):
    phase: str
    status: str  # "passed" | "failed" | "skipped"
    verdict: str | None = None
    details: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class RoleAssignment(BaseModel):
    role: str  # agent filename without .md
    phase: str  # DeliveryPhase value
    is_lead: bool = False


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class DeliveryState(BaseModel):
    delivery_phase: DeliveryPhase
    slug: str
    orchestration_mode: str = "classic"
    plan_path: str | None = None
    active_roles: list[str] = Field(default_factory=list)
    phase_lead: str | None = None
    skipped_phases: list[str] = Field(default_factory=list)
    phase_results: dict[str, PhaseResult] = Field(default_factory=dict)
    review_iteration: int = 0
    max_review_iterations: int = 3
    rules_snapshot_hash: str | None = None
    last_updated: str = Field(default_factory=_now_iso)
