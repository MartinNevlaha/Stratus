"""Pydantic models for the agent registry."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentEntry(BaseModel):
    """Metadata for a single agent."""

    name: str
    filename: str
    model: str  # "sonnet" | "opus" | "haiku"
    can_write: bool
    layer: str  # "core" | "process" | "engineering"
    phases: list[str]
    task_types: list[str] = Field(default_factory=list)
    applicable_stacks: list[str] | None = None  # None = universal
    orchestration_modes: list[str]  # ["default"] | ["swords"] | ["default", "swords"]
    optional: bool = False
    keywords: list[str] = Field(default_factory=list)
