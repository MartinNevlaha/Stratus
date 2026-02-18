"""Adaptive Learning Layer — Phase 5 of the stratus framework.

Public exports for the learning subsystem.
"""

from stratus.learning.analytics_db import AnalyticsDB
from stratus.learning.artifacts import (
    compute_artifact_path,
    create_artifact,
    generate_artifact_content,
)
from stratus.learning.config import LearningConfig, load_learning_config
from stratus.learning.database import LearningDatabase
from stratus.learning.models import (
    AnalysisResult,
    CandidateStatus,
    Decision,
    Detection,
    DetectionType,
    FailureCategory,
    FailureEvent,
    FailureTrend,
    FileHotspot,
    LLMAssessment,
    PatternCandidate,
    Proposal,
    ProposalStatus,
    ProposalType,
    RuleBaseline,
    RuleEffectiveness,
    Sensitivity,
)
from stratus.learning.watcher import ProjectWatcher

__all__ = [
    "AnalysisResult",
    "AnalyticsDB",
    "compute_artifact_path",
    "create_artifact",
    "generate_artifact_content",
    "CandidateStatus",
    "Decision",
    "Detection",
    "DetectionType",
    "FailureCategory",
    "FailureEvent",
    "FailureTrend",
    "FileHotspot",
    "LLMAssessment",
    "LearningConfig",
    "LearningDatabase",
    "PatternCandidate",
    "ProjectWatcher",
    "Proposal",
    "ProposalStatus",
    "ProposalType",
    "RuleBaseline",
    "RuleEffectiveness",
    "Sensitivity",
    "load_learning_config",
]
