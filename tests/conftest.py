"""Shared fixtures for stratus tests."""

import json
from pathlib import Path

import pytest


def _make_assistant_message(
    *,
    input_tokens: int = 1,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
    output_tokens: int = 100,
    timestamp: str = "2026-02-15T12:00:00.000Z",
    uuid: str = "aaaa",
) -> dict:
    """Build a minimal assistant-type JSONL entry with usage data."""
    return {
        "type": "assistant",
        "uuid": uuid,
        "timestamp": timestamp,
        "message": {
            "role": "assistant",
            "model": "claude-opus-4-6",
            "usage": {
                "input_tokens": input_tokens,
                "cache_creation_input_tokens": cache_creation_input_tokens,
                "cache_read_input_tokens": cache_read_input_tokens,
                "output_tokens": output_tokens,
            },
        },
    }


def _make_user_message(*, timestamp: str = "2026-02-15T11:59:00.000Z", uuid: str = "bbbb") -> dict:
    """Build a minimal user-type JSONL entry."""
    return {
        "type": "user",
        "uuid": uuid,
        "timestamp": timestamp,
        "message": {"role": "user", "content": "hello"},
    }


def _make_progress_message(
    *, timestamp: str = "2026-02-15T12:00:01.000Z", uuid: str = "cccc"
) -> dict:
    """Build a minimal progress-type JSONL entry."""
    return {
        "type": "progress",
        "uuid": uuid,
        "timestamp": timestamp,
        "data": {"type": "hook_progress"},
    }


def _make_compact_boundary(
    *,
    pre_tokens: int = 167000,
    trigger: str = "auto",
    timestamp: str = "2026-02-15T12:30:00.000Z",
    uuid: str = "dddd",
) -> dict:
    """Build a compact_boundary system message."""
    return {
        "type": "system",
        "subtype": "compact_boundary",
        "content": "Conversation compacted",
        "timestamp": timestamp,
        "uuid": uuid,
        "compactMetadata": {
            "trigger": trigger,
            "preTokens": pre_tokens,
        },
    }


def _write_jsonl(path: Path, entries: list[dict]) -> Path:
    """Write a list of dicts as JSONL to a file."""
    with open(path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
    return path


@pytest.fixture
def simple_transcript(tmp_path: Path) -> Path:
    """Transcript with 3 assistant messages, 1 user, 1 progress."""
    entries = [
        _make_user_message(uuid="u1"),
        _make_assistant_message(
            uuid="a1",
            input_tokens=2,
            cache_creation_input_tokens=55000,
            cache_read_input_tokens=0,
            output_tokens=500,
            timestamp="2026-02-15T12:00:00.000Z",
        ),
        _make_progress_message(uuid="p1"),
        _make_assistant_message(
            uuid="a2",
            input_tokens=1,
            cache_creation_input_tokens=6000,
            cache_read_input_tokens=55000,
            output_tokens=300,
            timestamp="2026-02-15T12:01:00.000Z",
        ),
        _make_assistant_message(
            uuid="a3",
            input_tokens=1,
            cache_creation_input_tokens=3000,
            cache_read_input_tokens=61000,
            output_tokens=200,
            timestamp="2026-02-15T12:02:00.000Z",
        ),
    ]
    return _write_jsonl(tmp_path / "simple.jsonl", entries)


@pytest.fixture
def transcript_with_compaction(tmp_path: Path) -> Path:
    """Transcript with assistant messages and a compaction event showing token drop."""
    entries = [
        _make_user_message(uuid="u1"),
        # Pre-compaction: tokens climbing
        _make_assistant_message(
            uuid="a1",
            input_tokens=2,
            cache_creation_input_tokens=80000,
            cache_read_input_tokens=0,
            output_tokens=500,
            timestamp="2026-02-15T12:00:00.000Z",
        ),
        _make_assistant_message(
            uuid="a2",
            input_tokens=1,
            cache_creation_input_tokens=10000,
            cache_read_input_tokens=80000,
            output_tokens=400,
            timestamp="2026-02-15T12:05:00.000Z",
        ),
        _make_assistant_message(
            uuid="a3",
            input_tokens=1,
            cache_creation_input_tokens=77000,
            cache_read_input_tokens=0,
            output_tokens=300,
            timestamp="2026-02-15T12:09:00.000Z",
        ),
        # Compaction event at 167K tokens
        _make_compact_boundary(
            pre_tokens=167000,
            timestamp="2026-02-15T12:10:00.000Z",
            uuid="cb1",
        ),
        # Post-compaction: tokens reset lower
        _make_user_message(uuid="u2", timestamp="2026-02-15T12:10:01.000Z"),
        _make_assistant_message(
            uuid="a4",
            input_tokens=2,
            cache_creation_input_tokens=40000,
            cache_read_input_tokens=0,
            output_tokens=200,
            timestamp="2026-02-15T12:11:00.000Z",
        ),
    ]
    return _write_jsonl(tmp_path / "compaction.jsonl", entries)


@pytest.fixture
def empty_transcript(tmp_path: Path) -> Path:
    """Empty JSONL file."""
    return _write_jsonl(tmp_path / "empty.jsonl", [])


@pytest.fixture
def transcript_missing_usage(tmp_path: Path) -> Path:
    """Transcript with an assistant message that has no usage field."""
    entries = [
        _make_user_message(uuid="u1"),
        {
            "type": "assistant",
            "uuid": "a1",
            "timestamp": "2026-02-15T12:00:00.000Z",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "hello"}],
                # No usage field
            },
        },
        _make_assistant_message(
            uuid="a2",
            input_tokens=1,
            cache_creation_input_tokens=50000,
            cache_read_input_tokens=0,
            output_tokens=100,
            timestamp="2026-02-15T12:01:00.000Z",
        ),
    ]
    return _write_jsonl(tmp_path / "missing_usage.jsonl", entries)
