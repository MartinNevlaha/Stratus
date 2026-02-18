"""Pydantic models and enums for the adaptive learning layer."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class DetectionType(StrEnum):
    CODE_PATTERN = "code_pattern"
    STRUCTURAL_CHANGE = "structural_change"
    FIX_PATTERN = "fix_pattern"
    IMPORT_PATTERN = "import_pattern"
    CONFIG_PATTERN = "config_pattern"
    SERVICE_DETECTED = "service_detected"


class CandidateStatus(StrEnum):
    PENDING = "pending"
    INTERPRETED = "interpreted"
    PROPOSED = "proposed"
    DECIDED = "decided"


class ProposalType(StrEnum):
    RULE = "rule"
    SKILL = "skill"
    ADR = "adr"
    PROJECT_GRAPH = "project_graph"
    TEMPLATE = "template"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    PRESENTED = "presented"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    IGNORED = "ignored"
    SNOOZED = "snoozed"


class Decision(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    IGNORE = "ignore"
    SNOOZE = "snooze"


class Sensitivity(StrEnum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _description_hash(description: str) -> str:
    return hashlib.sha256(description.encode()).hexdigest()[:16]


class Detection(BaseModel):
    type: DetectionType
    count: int
    confidence_raw: float = Field(ge=0.0, le=1.0)
    files: list[str]
    description: str
    instances: list[dict] = Field(default_factory=list)


class LLMAssessment(BaseModel):
    is_pattern: bool
    confidence: float = Field(ge=0.0, le=1.0)
    proposed_rule: str | None = None
    reasoning: str | None = None


class PatternCandidate(BaseModel):
    id: str
    detection_type: DetectionType
    count: int
    confidence_raw: float = Field(ge=0.0, le=1.0)
    confidence_final: float = Field(ge=0.0, le=1.0)
    files: list[str]
    description: str
    instances: list[dict] = Field(default_factory=list)
    detected_at: str = Field(default_factory=_now_iso)
    status: CandidateStatus = CandidateStatus.PENDING
    llm_assessment: LLMAssessment | None = None
    description_hash: str | None = None

    def model_post_init(self, __context: object) -> None:
        if self.description_hash is None:
            self.description_hash = _description_hash(self.description)


class Proposal(BaseModel):
    id: str
    candidate_id: str
    type: ProposalType
    title: str
    description: str
    proposed_content: str
    proposed_path: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    status: ProposalStatus = ProposalStatus.PENDING
    presented_at: str | None = None
    decided_at: str | None = None
    decision: Decision | None = None
    edited_content: str | None = None
    session_id: str | None = None


class AnalysisResult(BaseModel):
    detections: list[Detection]
    analyzed_commits: int
    analysis_time_ms: int


# --- Phase 5.1: Analytics models ---


class FailureCategory(StrEnum):
    LINT_ERROR = "lint_error"
    MISSING_TEST = "missing_test"
    CONTEXT_OVERFLOW = "context_overflow"
    REVIEW_FAILURE = "review_failure"


def _failure_signature(category: str, file_path: str | None, detail: str) -> str:
    """Deterministic dedup key: hash of category + file_path + detail[:200] + day."""
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    raw = f"{category}|{file_path or ''}|{detail[:200]}|{day}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class FailureEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: FailureCategory
    file_path: str | None = None
    detail: str = ""
    session_id: str | None = None
    recorded_at: str = Field(default_factory=_now_iso)
    signature: str = ""

    def model_post_init(self, __context: object) -> None:
        if not self.signature:
            self.signature = _failure_signature(
                self.category, self.file_path, self.detail,
            )


class RuleBaseline(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    proposal_id: str
    rule_path: str
    category: FailureCategory
    baseline_count: int
    baseline_window_days: int = 30
    created_at: str = Field(default_factory=_now_iso)
    category_source: str = "heuristic"


class RuleEffectiveness(BaseModel):
    proposal_id: str
    rule_path: str
    category: FailureCategory
    baseline_rate: float
    current_rate: float
    effectiveness_score: float
    sample_days: int
    verdict: str


class FailureTrend(BaseModel):
    category: FailureCategory
    period: str
    count: int


class FileHotspot(BaseModel):
    file_path: str
    total_failures: int
    by_category: dict[str, int]
