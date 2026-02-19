"""Pydantic models for memory events and sessions."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ActorType(StrEnum):
    USER = "user"
    AGENT = "agent"
    HOOK = "hook"
    SYSTEM = "system"


class ScopeType(StrEnum):
    REPO = "repo"
    GLOBAL = "global"
    USER = "user"


class EventType(StrEnum):
    BUGFIX = "bugfix"
    FEATURE = "feature"
    REFACTOR = "refactor"
    DISCOVERY = "discovery"
    DECISION = "decision"
    CHANGE = "change"
    PATTERN_CANDIDATE = "pattern_candidate"
    SKILL_SUGGESTION = "skill_suggestion"
    RULE_PROPOSAL = "rule_proposal"
    LEARNING_DECISION = "learning_decision"
    REJECTED_PATTERN = "rejected_pattern"
    SPEC_STARTED = "spec_started"
    SPEC_COMPLETED = "spec_completed"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _now_epoch_ms() -> int:
    return int(time.time() * 1000)


class MemoryEvent(BaseModel):
    id: int | None = None
    ts: str = Field(default_factory=_now_iso)
    actor: ActorType = ActorType.AGENT
    scope: ScopeType = ScopeType.REPO
    type: EventType = EventType.DISCOVERY
    text: str
    title: str | None = None
    tags: list[str] = Field(default_factory=list)
    refs: dict = Field(default_factory=dict)
    ttl: str | None = None
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    dedupe_key: str | None = None
    project: str | None = None
    session_id: str | None = None
    created_at_epoch: int = Field(default_factory=_now_epoch_ms)


class Session(BaseModel):
    id: int | None = None
    content_session_id: str
    project: str
    initial_prompt: str | None = None
    started_at: str = Field(default_factory=_now_iso)
