"""Tests for SQLite schema and migrations."""

import sqlite3

import pytest

from stratus.memory.schema import get_current_version, run_migrations


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


class TestRunMigrations:
    def test_creates_schema_versions_table(self, db: sqlite3.Connection):
        run_migrations(db)
        tables = {
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "schema_versions" in tables

    def test_creates_memory_events_table(self, db: sqlite3.Connection):
        run_migrations(db)
        tables = {
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "memory_events" in tables

    def test_creates_sessions_table(self, db: sqlite3.Connection):
        run_migrations(db)
        tables = {
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "sessions" in tables

    def test_creates_fts5_virtual_table(self, db: sqlite3.Connection):
        run_migrations(db)
        tables = {
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "memory_events_fts" in tables

    def test_fts5_tokenizer_works(self, db: sqlite3.Connection):
        run_migrations(db)
        # Insert a row into memory_events; trigger should populate FTS
        db.execute(
            """INSERT INTO memory_events
               (ts, actor, scope, type, text, title, tags, refs, importance, created_at_epoch)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "2026-01-01T00:00:00Z",
                "agent",
                "repo",
                "discovery",
                "discovered a running bug in auth module",
                "Auth bug",
                "[]",
                "{}",
                0.5,
                1000000,
            ),
        )
        db.commit()
        # FTS5 porter stemming: "running" should match "run"
        results = db.execute(
            "SELECT * FROM memory_events_fts WHERE memory_events_fts MATCH 'run'"
        ).fetchall()
        assert len(results) == 1

    def test_dedupe_key_unique_constraint(self, db: sqlite3.Connection):
        run_migrations(db)
        row = (
            "2026-01-01T00:00:00Z",
            "agent",
            "repo",
            "discovery",
            "text1",
            "title1",
            "[]",
            "{}",
            0.5,
            1000000,
            "dedupe-abc",
        )
        db.execute(
            """INSERT INTO memory_events
               (ts, actor, scope, type, text, title, tags, refs, importance,
                created_at_epoch, dedupe_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            row,
        )
        db.commit()
        # Second insert with same dedupe_key should conflict
        row2 = (
            "2026-01-02T00:00:00Z",
            "user",
            "global",
            "bugfix",
            "text2",
            "title2",
            "[]",
            "{}",
            0.7,
            2000000,
            "dedupe-abc",
        )
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                """INSERT INTO memory_events
                   (ts, actor, scope, type, text, title, tags, refs, importance,
                    created_at_epoch, dedupe_key)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                row2,
            )

    def test_idempotent_rerun(self, db: sqlite3.Connection):
        run_migrations(db)
        v1 = get_current_version(db)
        run_migrations(db)
        v2 = get_current_version(db)
        assert v1 == v2

    def test_version_tracked(self, db: sqlite3.Connection):
        run_migrations(db)
        version = get_current_version(db)
        assert version >= 1

    def test_wal_mode_enabled(self, tmp_path):
        # WAL mode only works with file-backed databases, not :memory:
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        run_migrations(conn)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        conn.close()

    def test_foreign_keys_enabled(self, db: sqlite3.Connection):
        run_migrations(db)
        fk = db.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1

    def test_memory_events_indexes_exist(self, db: sqlite3.Connection):
        run_migrations(db)
        indexes = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='memory_events'"
            ).fetchall()
        }
        assert "idx_memory_events_ts" in indexes
        assert "idx_memory_events_type" in indexes
        assert "idx_memory_events_project" in indexes

    def test_fts_insert_trigger_exists(self, db: sqlite3.Connection):
        run_migrations(db)
        triggers = {
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()
        }
        assert "memory_events_ai" in triggers

    def test_fts_delete_trigger_exists(self, db: sqlite3.Connection):
        run_migrations(db)
        triggers = {
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()
        }
        assert "memory_events_ad" in triggers
