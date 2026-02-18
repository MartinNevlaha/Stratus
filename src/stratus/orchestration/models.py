"""Pydantic models and enums for the orchestration layer."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SpecPhase(StrEnum):
    PLAN = "plan"
    IMPLEMENT = "implement"
    VERIFY = "verify"
    LEARN = "learn"


class PlanStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    IMPLEMENTING = "implementing"
    VERIFYING = "verifying"
    COMPLETE = "complete"
    FAILED = "failed"


class Verdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class FindingSeverity(StrEnum):
    MUST_FIX = "must_fix"
    SHOULD_FIX = "should_fix"
    SUGGESTION = "suggestion"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class ReviewFinding(BaseModel):
    file_path: str
    line: int | None = None
    severity: FindingSeverity
    description: str


class ReviewVerdict(BaseModel):
    reviewer: str
    verdict: Verdict
    findings: list[ReviewFinding] = Field(default_factory=list)
    raw_output: str


class WorktreeInfo(BaseModel):
    path: str
    branch: str
    base_branch: str
    slug: str


class OrchestratorMode(StrEnum):
    TASK_TOOL = "task-tool"
    AGENT_TEAMS = "agent-teams"


class TeammateStatus(StrEnum):
    IDLE = "idle"
    WORKING = "working"
    SHUTTING_DOWN = "shutting_down"
    ERROR = "error"


class TeamConfig(BaseModel):
    name: str = ""
    mode: OrchestratorMode = OrchestratorMode.TASK_TOOL
    teammate_mode: str = "auto"
    delegate_mode: bool = False
    require_plan_approval: bool = True
    max_teammates: int = 5


class TeammateInfo(BaseModel):
    name: str
    agent_type: str
    agent_id: str | None = None
    status: TeammateStatus = TeammateStatus.IDLE
    current_task: str | None = None


class TeamState(BaseModel):
    config: TeamConfig
    teammates: list[TeammateInfo] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now_iso)
    lead_session_id: str | None = None


class SpecState(BaseModel):
    phase: SpecPhase
    slug: str
    plan_path: str | None = None
    plan_status: PlanStatus = PlanStatus.PENDING
    worktree: WorktreeInfo | None = None
    current_task: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    review_iteration: int = 0
    max_review_iterations: int = 3
    last_updated: str = Field(default_factory=_now_iso)
