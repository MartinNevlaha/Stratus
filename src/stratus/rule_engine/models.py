"""Pydantic models and enums for the rule engine layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class RuleSource(StrEnum):
    PROJECT = "project"  # .claude/rules/*.md
    CLAUDE_MD = "claude_md"  # CLAUDE.md
    FRAMEWORK = "framework"  # Framework invariants
    LEARNING = "learning"  # Learning-generated rules


class Rule(BaseModel):
    name: str
    source: RuleSource
    content: str
    path: str
    content_hash: str = ""


class RulesSnapshot(BaseModel):
    rules: list[Rule] = Field(default_factory=list)
    snapshot_hash: str = ""


class Invariant(BaseModel):
    id: str
    title: str
    content: str
    disablable: bool = True


class ImmutabilityViolation(BaseModel):
    rule_name: str
    change_type: str  # "added" | "removed" | "modified"
    details: str = ""


@dataclass
class InvariantContext:
    """Context for invariant validation."""

    project_root: Path | None = None
    previous_rules_snapshot: RulesSnapshot | None = None
    spec_active: bool = False
    disabled_ids: list[str] = field(default_factory=list)


class InvariantViolation(BaseModel):
    """A concrete violation found during invariant validation."""

    invariant_id: str
    message: str
    file_path: str | None = None
