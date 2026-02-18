"""Tests for Database CRUD and FTS5 search."""

import pytest

from stratus.memory.database import Database
from stratus.memory.models import EventType, MemoryEvent


@pytest.fixture
def db():
    database = Database(":memory:")
    yield database
    database.close()


class TestSaveEvent:
    def test_save_and_retrieve(self, db: Database):
        event = MemoryEvent(text="found a bug in auth", title="Auth bug")
        event_id = db.save_event(event)
        assert event_id >= 1

        results = db.get_events([event_id])
        assert len(results) == 1
        assert results[0].text == "found a bug in auth"
        assert results[0].title == "Auth bug"
        assert results[0].id == event_id

    def test_save_preserves_all_fields(self, db: Database):
        event = MemoryEvent(
            text="fix login",
            title="Login fix",
            type=EventType.BUGFIX,
            tags=["auth", "critical"],
            refs={"files": ["auth.py"]},
            importance=0.9,
            project="my-project",
            session_id="sess-1",
            dedupe_key="dedup-123",
        )
        event_id = db.save_event(event)
        results = db.get_events([event_id])
        r = results[0]
        assert r.type == EventType.BUGFIX
        assert r.tags == ["auth", "critical"]
        assert r.refs == {"files": ["auth.py"]}
        assert r.importance == 0.9
        assert r.project == "my-project"
        assert r.session_id == "sess-1"
        assert r.dedupe_key == "dedup-123"

    def test_dedupe_upsert(self, db: Database):
        e1 = MemoryEvent(text="first version", dedupe_key="key-1")
        id1 = db.save_event(e1)

        e2 = MemoryEvent(text="second version", dedupe_key="key-1")
        id2 = db.save_event(e2)

        # Should return the same ID (upsert)
        assert id1 == id2
        results = db.get_events([id1])
        assert results[0].text == "second version"


class TestSearch:
    def test_search_basic(self, db: Database):
        db.save_event(MemoryEvent(text="authentication bug in login form"))
        db.save_event(MemoryEvent(text="database migration script"))
        db.save_event(MemoryEvent(text="login page redesign"))

        results = db.search("login")
        assert len(results) >= 2
        texts = [r.text for r in results]
        assert any("login" in t for t in texts)

    def test_search_fts5_stemming(self, db: Database):
        db.save_event(MemoryEvent(text="the users were running tests"))
        results = db.search("run")
        assert len(results) == 1
        assert "running" in results[0].text

    def test_search_by_type(self, db: Database):
        db.save_event(MemoryEvent(text="bug in auth", type=EventType.BUGFIX))
        db.save_event(MemoryEvent(text="new feature", type=EventType.FEATURE))

        results = db.search("bug auth", type=EventType.BUGFIX)
        assert len(results) == 1
        assert results[0].type == EventType.BUGFIX

    def test_search_by_project(self, db: Database):
        db.save_event(MemoryEvent(text="project A thing", project="proj-a"))
        db.save_event(MemoryEvent(text="project B thing", project="proj-b"))

        results = db.search("thing", project="proj-a")
        assert len(results) == 1
        assert results[0].project == "proj-a"

    def test_search_by_scope(self, db: Database):
        db.save_event(MemoryEvent(text="global config", scope="global"))
        db.save_event(MemoryEvent(text="repo config", scope="repo"))

        results = db.search("config", scope="global")
        assert len(results) == 1
        assert results[0].scope == "global"

    def test_search_with_limit(self, db: Database):
        for i in range(10):
            db.save_event(MemoryEvent(text=f"search result item {i}"))

        results = db.search("item", limit=3)
        assert len(results) == 3

    def test_search_with_offset(self, db: Database):
        for i in range(5):
            db.save_event(MemoryEvent(text=f"search result item {i}"))

        all_results = db.search("item", limit=100)
        offset_results = db.search("item", limit=100, offset=2)
        assert len(offset_results) == len(all_results) - 2

    def test_search_empty_db(self, db: Database):
        results = db.search("anything")
        assert results == []

    def test_search_no_match(self, db: Database):
        db.save_event(MemoryEvent(text="something unrelated"))
        results = db.search("xyznonexistent")
        assert results == []

    def test_search_by_date_range(self, db: Database):
        db.save_event(
            MemoryEvent(
                text="old event",
                ts="2026-01-01T00:00:00Z",
            )
        )
        db.save_event(
            MemoryEvent(
                text="new event",
                ts="2026-02-15T00:00:00Z",
            )
        )

        results = db.search("event", date_start="2026-02-01T00:00:00Z")
        assert len(results) == 1
        assert results[0].text == "new event"


class TestTimeline:
    def test_timeline_around_anchor(self, db: Database):
        ids = []
        for i in range(10):
            eid = db.save_event(
                MemoryEvent(
                    text=f"event {i}",
                    ts=f"2026-01-01T{i:02d}:00:00Z",
                )
            )
            ids.append(eid)

        # Get timeline around event 5
        timeline = db.timeline(anchor_id=ids[5], depth_before=2, depth_after=2)
        assert len(timeline) == 5  # 2 before + anchor + 2 after
        texts = [e.text for e in timeline]
        assert texts == ["event 3", "event 4", "event 5", "event 6", "event 7"]

    def test_timeline_at_start(self, db: Database):
        ids = []
        for i in range(5):
            eid = db.save_event(
                MemoryEvent(
                    text=f"event {i}",
                    ts=f"2026-01-01T{i:02d}:00:00Z",
                )
            )
            ids.append(eid)

        timeline = db.timeline(anchor_id=ids[0], depth_before=3, depth_after=1)
        assert len(timeline) == 2  # anchor + 1 after (none before)
        assert timeline[0].text == "event 0"

    def test_timeline_at_end(self, db: Database):
        ids = []
        for i in range(5):
            eid = db.save_event(
                MemoryEvent(
                    text=f"event {i}",
                    ts=f"2026-01-01T{i:02d}:00:00Z",
                )
            )
            ids.append(eid)

        timeline = db.timeline(anchor_id=ids[4], depth_before=1, depth_after=3)
        assert len(timeline) == 2  # 1 before + anchor (none after)
        assert timeline[-1].text == "event 4"

    def test_timeline_with_project_filter(self, db: Database):
        for i in range(5):
            db.save_event(
                MemoryEvent(
                    text=f"a-{i}",
                    project="a",
                    ts=f"2026-01-01T{i:02d}:00:00Z",
                )
            )
        mid_id = db.save_event(
            MemoryEvent(
                text="b-0",
                project="b",
                ts="2026-01-01T02:30:00Z",
            )
        )

        timeline = db.timeline(anchor_id=mid_id, depth_before=2, depth_after=2, project="b")
        assert len(timeline) == 1  # Only the anchor matches project b


class TestGetEvents:
    def test_batch_fetch(self, db: Database):
        id1 = db.save_event(MemoryEvent(text="first"))
        db.save_event(MemoryEvent(text="second"))
        id3 = db.save_event(MemoryEvent(text="third"))

        results = db.get_events([id1, id3])
        assert len(results) == 2
        texts = {r.text for r in results}
        assert texts == {"first", "third"}

    def test_batch_with_missing_ids(self, db: Database):
        id1 = db.save_event(MemoryEvent(text="exists"))
        results = db.get_events([id1, 9999])
        assert len(results) == 1
        assert results[0].text == "exists"

    def test_batch_empty_ids(self, db: Database):
        results = db.get_events([])
        assert results == []


class TestSessions:
    def test_init_session(self, db: Database):
        session = db.init_session("cs-123", "my-project", "fix the bug")
        assert session.id is not None
        assert session.content_session_id == "cs-123"
        assert session.project == "my-project"
        assert session.initial_prompt == "fix the bug"

    def test_list_sessions(self, db: Database):
        db.init_session("cs-1", "proj-a", "prompt 1")
        db.init_session("cs-2", "proj-b", "prompt 2")
        db.init_session("cs-3", "proj-a", "prompt 3")

        sessions = db.list_sessions()
        assert len(sessions) == 3

    def test_list_sessions_with_limit(self, db: Database):
        for i in range(5):
            db.init_session(f"cs-{i}", "proj", f"prompt {i}")

        sessions = db.list_sessions(limit=2)
        assert len(sessions) == 2

    def test_list_sessions_with_offset(self, db: Database):
        for i in range(5):
            db.init_session(f"cs-{i}", "proj", f"prompt {i}")

        sessions = db.list_sessions(limit=100, offset=3)
        assert len(sessions) == 2


class TestGetStats:
    def test_stats_empty_db(self, db: Database):
        stats = db.get_stats()
        assert stats["total_events"] == 0
        assert stats["total_sessions"] == 0

    def test_stats_with_data(self, db: Database):
        db.save_event(MemoryEvent(text="event 1", type=EventType.BUGFIX))
        db.save_event(MemoryEvent(text="event 2", type=EventType.FEATURE))
        db.save_event(MemoryEvent(text="event 3", type=EventType.BUGFIX))
        db.init_session("cs-1", "proj", "prompt")

        stats = db.get_stats()
        assert stats["total_events"] == 3
        assert stats["total_sessions"] == 1
        assert stats["events_by_type"]["bugfix"] == 2
        assert stats["events_by_type"]["feature"] == 1
