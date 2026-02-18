"""Parse Claude Code JSONL transcripts and estimate context usage."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TokenUsage:
    """Per-message token counts from the API response."""

    input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_input(self) -> int:
        return self.input_tokens + self.cache_creation_input_tokens + self.cache_read_input_tokens


@dataclass
class CompactionEvent:
    """A context compaction boundary from the transcript."""

    timestamp: str
    trigger: str
    pre_tokens: int


@dataclass
class TranscriptStats:
    """Summary statistics for a parsed transcript session."""

    usages: list[TokenUsage] = field(default_factory=list)
    compaction_events: list[CompactionEvent] = field(default_factory=list)

    @property
    def message_count(self) -> int:
        return len(self.usages)

    @property
    def compaction_count(self) -> int:
        return len(self.compaction_events)

    @property
    def peak_tokens(self) -> int:
        if not self.usages:
            return 0
        return max(u.total_input for u in self.usages)

    @property
    def final_tokens(self) -> int:
        if not self.usages:
            return 0
        return self.usages[-1].total_input


def parse_transcript(path: Path) -> TranscriptStats:
    """Read a JSONL transcript and extract token usage from assistant messages."""
    stats = TranscriptStats()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)

            if entry.get("type") == "system" and entry.get("subtype") == "compact_boundary":
                metadata = entry.get("compactMetadata", {})
                stats.compaction_events.append(
                    CompactionEvent(
                        timestamp=entry.get("timestamp", ""),
                        trigger=metadata.get("trigger", "unknown"),
                        pre_tokens=metadata.get("preTokens", 0),
                    )
                )
                continue

            if entry.get("type") != "assistant":
                continue

            message = entry.get("message", {})
            usage = message.get("usage")
            if usage is None:
                continue

            stats.usages.append(
                TokenUsage(
                    input_tokens=usage.get("input_tokens", 0),
                    cache_creation_input_tokens=usage.get("cache_creation_input_tokens", 0),
                    cache_read_input_tokens=usage.get("cache_read_input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                )
            )

    return stats


def find_compaction_events(path: Path) -> list[CompactionEvent]:
    """Extract all compact_boundary events from a transcript."""
    events: list[CompactionEvent] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if entry.get("type") == "system" and entry.get("subtype") == "compact_boundary":
                metadata = entry.get("compactMetadata", {})
                events.append(
                    CompactionEvent(
                        timestamp=entry.get("timestamp", ""),
                        trigger=metadata.get("trigger", "unknown"),
                        pre_tokens=metadata.get("preTokens", 0),
                    )
                )
    return events


def estimate_context_pct(total_tokens: int, context_window: int = 200_000) -> float:
    """Calculate raw context usage as a percentage."""
    if context_window == 0:
        return 0.0
    return (total_tokens / context_window) * 100


def to_effective_pct(raw_pct: float, threshold: float = 83.5) -> float:
    """Normalize raw percentage to effective scale (threshold=100%)."""
    if threshold == 0:
        return 0.0
    return (raw_pct / threshold) * 100
