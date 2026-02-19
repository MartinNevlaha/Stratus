"""Tests for memory event and session pydantic models."""

from datetime import datetime

import pytest

from stratus.memory.models import (
    ActorType,
    EventType,
    MemoryEvent,
    ScopeType,
    Session,
)


class TestMemoryEvent:
    def test_create_minimal_event(self):
        event = MemoryEvent(text="discovered bug in auth")
        assert event.text == "discovered bug in auth"
        assert event.type == EventType.DISCOVERY
        assert event.actor == ActorType.AGENT
        assert event.scope == ScopeType.REPO
        assert event.importance == 0.5
        assert event.tags == []

    def test_create_full_event(self):
        event = MemoryEvent(
            text="fixed null pointer in login",
            title="Fix login NPE",
            type=EventType.BUGFIX,
            actor=ActorType.USER,
            scope=ScopeType.GLOBAL,
            tags=["auth", "critical"],
            refs={"files": ["src/auth.py"], "commits": ["abc123"]},
            importance=0.9,
            project="my-app",
            session_id="sess-001",
            dedupe_key="sha256-abc",
            ttl="2026-12-31T23:59:59Z",
        )
        assert event.title == "Fix login NPE"
        assert event.type == EventType.BUGFIX
        assert event.actor == ActorType.USER
        assert event.scope == ScopeType.GLOBAL
        assert event.tags == ["auth", "critical"]
        assert event.refs["files"] == ["src/auth.py"]
        assert event.importance == 0.9
        assert event.project == "my-app"
        assert event.session_id == "sess-001"

    def test_event_ts_auto_generated(self):
        event = MemoryEvent(text="test")
        assert event.ts is not None
        # Should be a valid ISO 8601 datetime string
        parsed = datetime.fromisoformat(event.ts)
        assert parsed.tzinfo is not None

    def test_event_serialization_roundtrip(self):
        event = MemoryEvent(
            text="test event",
            title="Test",
            type=EventType.FEATURE,
            tags=["tag1"],
            refs={"files": ["a.py"]},
        )
        data = event.model_dump()
        assert data["text"] == "test event"
        assert data["type"] == "feature"
        assert data["tags"] == ["tag1"]

        restored = MemoryEvent.model_validate(data)
        assert restored.text == event.text
        assert restored.type == event.type

    def test_event_json_roundtrip(self):
        event = MemoryEvent(text="json test", type=EventType.DECISION)
        json_str = event.model_dump_json()
        restored = MemoryEvent.model_validate_json(json_str)
        assert restored.text == event.text
        assert restored.type == EventType.DECISION

    def test_event_type_enum_values(self):
        valid_types = [
            "bugfix",
            "feature",
            "refactor",
            "discovery",
            "decision",
            "change",
            "pattern_candidate",
            "skill_suggestion",
            "rule_proposal",
            "learning_decision",
            "rejected_pattern",
        ]
        for t in valid_types:
            event = MemoryEvent(text="test", type=EventType(t))
            assert event.type == EventType(t)

    def test_event_invalid_type_raises(self):
        with pytest.raises(ValueError):
            MemoryEvent(text="test", type=EventType("invalid_type"))  # type: ignore[arg-type]

    def test_event_importance_bounds(self):
        event_low = MemoryEvent(text="t", importance=0.0)
        assert event_low.importance == 0.0
        event_high = MemoryEvent(text="t", importance=1.0)
        assert event_high.importance == 1.0

    def test_event_importance_out_of_range_raises(self):
        with pytest.raises(ValueError):
            MemoryEvent(text="t", importance=1.5)
        with pytest.raises(ValueError):
            MemoryEvent(text="t", importance=-0.1)

    def test_event_dedupe_key_optional(self):
        event = MemoryEvent(text="no dedupe")
        assert event.dedupe_key is None

    def test_event_with_id(self):
        event = MemoryEvent(id=42, text="with id")
        assert event.id == 42

    def test_event_refs_defaults_empty(self):
        event = MemoryEvent(text="test")
        assert event.refs == {}

    def test_event_created_at_epoch_auto(self):
        event = MemoryEvent(text="test")
        assert event.created_at_epoch is not None
        assert isinstance(event.created_at_epoch, int)
        assert event.created_at_epoch > 0


class TestSession:
    def test_create_session(self):
        session = Session(
            content_session_id="cs-123",
            project="my-project",
        )
        assert session.content_session_id == "cs-123"
        assert session.project == "my-project"
        assert session.started_at is not None

    def test_session_with_prompt(self):
        session = Session(
            content_session_id="cs-456",
            project="proj",
            initial_prompt="Fix the login bug",
        )
        assert session.initial_prompt == "Fix the login bug"

    def test_session_serialization(self):
        session = Session(
            content_session_id="cs-789",
            project="proj",
            initial_prompt="do something",
        )
        data = session.model_dump()
        assert data["content_session_id"] == "cs-789"
        restored = Session.model_validate(data)
        assert restored.content_session_id == session.content_session_id

    def test_session_id_optional(self):
        session = Session(content_session_id="cs-1", project="p")
        assert session.id is None

    def test_session_with_id(self):
        session = Session(id=10, content_session_id="cs-1", project="p")
        assert session.id == 10


class TestEnums:
    def test_actor_types(self):
        assert ActorType.USER == "user"
        assert ActorType.AGENT == "agent"
        assert ActorType.HOOK == "hook"
        assert ActorType.SYSTEM == "system"

    def test_scope_types(self):
        assert ScopeType.REPO == "repo"
        assert ScopeType.GLOBAL == "global"
        assert ScopeType.USER == "user"

    def test_event_types_complete(self):
        assert len(EventType) == 13
        assert EventType.SPEC_STARTED == "spec_started"
        assert EventType.SPEC_COMPLETED == "spec_completed"
