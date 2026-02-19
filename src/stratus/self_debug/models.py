"""Pydantic models and enums for the self-debug sandbox."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class IssueType(StrEnum):
    BARE_EXCEPT = "bare_except"
    UNUSED_IMPORT = "unused_import"
    MISSING_TYPE_HINT = "missing_type_hint"
    DEAD_CODE = "dead_code"
    ERROR_HANDLING = "error_handling"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GovernanceImpact(StrEnum):
    NONE = "none"
    CRITICAL = "critical"


class Issue(BaseModel):
    id: str
    type: IssueType
    file_path: str
    line_start: int
    line_end: int
    description: str
    suggestion: str


class PatchProposal(BaseModel):
    issue_id: str
    file_path: str
    unified_diff: str
    risk: RiskLevel
    governance_impact: GovernanceImpact
    tests_affected: list[str] = Field(default_factory=list)


class DebugReport(BaseModel):
    issues: list[Issue]
    patches: list[PatchProposal]
    analyzed_files: int
    skipped_files: int
    analysis_time_ms: int
