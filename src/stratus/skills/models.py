"""Pydantic models for the skills system."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SkillSource(StrEnum):
    LOCAL = "local"
    BUILTIN = "builtin"
    LEARNING = "learning"


class SkillManifest(BaseModel):
    # Required (Claude Code standard)
    name: str
    description: str
    agent: str
    context: str = "fork"
    # Extended (optional, backward-compatible)
    version: str | None = None
    requires: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    priority: int = 0
    tags: list[str] = Field(default_factory=list)
    requires_phase: str | None = None
    source: str = "local"
    min_framework_version: str | None = None
    # Computed (not in frontmatter)
    body: str = ""
    path: str = ""
    content_hash: str = ""


class SkillValidationError(BaseModel):
    skill_name: str
    message: str


class SkillConflict(BaseModel):
    name: str
    sources: list[str]
    winner: str
