"""Tests for learning/schema.py — DDL and migrations."""

from __future__ import annotations

import sqlite3

import pytest

from stratus.learning.schema import (
    MIGRATIONS,
    _get_current_version,
    _run_migrations,
)


def _make_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    return db


class TestMigrations:
    def test_migrations_dict_not_empty(self):
        assert len(MIGRATIONS) >= 1

    def test_run_migrations_creates_tables(self):
        db = _make_db()
        _run_migrations(db)
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "pattern_candidates" in tables
        assert "proposals" in tables
        assert "analysis_state" in tables
        assert "schema_versions" in tables
        db.close()

    def test_run_migrations_idempotent(self):
        db = _make_db()
        _run_migrations(db)
        _run_migrations(db)
        version = _get_current_version(db)
        assert version >= 1
        db.close()

    def test_get_current_version_zero_before_migrations(self):
        db = _make_db()
        assert _get_current_version(db) == 0
        db.close()

    def test_get_current_version_after_migrations(self):
        db = _make_db()
        _run_migrations(db)
        assert _get_current_version(db) >= 1
        db.close()

    def test_pattern_candidates_columns(self):
        db = _make_db()
        _run_migrations(db)
        cursor = db.execute("PRAGMA table_info(pattern_candidates)")
        cols = {row[1] for row in cursor.fetchall()}
        expected = {
            "id", "detection_type", "count", "confidence_raw",
            "confidence_final", "files", "description", "instances",
            "detected_at", "status", "llm_assessment", "description_hash",
        }
        assert expected.issubset(cols)
        db.close()

    def test_proposals_columns(self):
        db = _make_db()
        _run_migrations(db)
        cursor = db.execute("PRAGMA table_info(proposals)")
        cols = {row[1] for row in cursor.fetchall()}
        expected = {
            "id", "candidate_id", "type", "title", "description",
            "proposed_content", "proposed_path", "confidence", "status",
            "presented_at", "decided_at", "decision", "edited_content",
            "session_id",
        }
        assert expected.issubset(cols)
        db.close()

    def test_analysis_state_columns(self):
        db = _make_db()
        _run_migrations(db)
        cursor = db.execute("PRAGMA table_info(analysis_state)")
        cols = {row[1] for row in cursor.fetchall()}
        expected = {"id", "last_commit", "last_analyzed_at", "total_commits_analyzed"}
        assert expected.issubset(cols)
        db.close()

    def test_analysis_state_single_row_constraint(self):
        db = _make_db()
        _run_migrations(db)
        db.execute(
            """INSERT INTO analysis_state
               (id, last_commit, total_commits_analyzed)
               VALUES (1, 'abc', 0)""",
        )
        db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                """INSERT INTO analysis_state
                   (id, last_commit, total_commits_analyzed)
                   VALUES (2, 'def', 0)""",
            )
        db.close()


class TestMigration2:
    def test_migration_2_creates_failure_events(self):
        db = _make_db()
        _run_migrations(db)
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "failure_events" in tables
        db.close()

    def test_migration_2_creates_rule_baselines(self):
        db = _make_db()
        _run_migrations(db)
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "rule_baselines" in tables
        db.close()

    def test_failure_events_columns(self):
        db = _make_db()
        _run_migrations(db)
        cursor = db.execute("PRAGMA table_info(failure_events)")
        cols = {row[1] for row in cursor.fetchall()}
        expected = {
            "id", "category", "file_path", "detail",
            "session_id", "recorded_at", "signature",
        }
        assert expected.issubset(cols)
        db.close()

    def test_rule_baselines_columns(self):
        db = _make_db()
        _run_migrations(db)
        cursor = db.execute("PRAGMA table_info(rule_baselines)")
        cols = {row[1] for row in cursor.fetchall()}
        expected = {
            "id", "proposal_id", "rule_path", "category",
            "baseline_count", "baseline_window_days",
            "created_at", "category_source",
        }
        assert expected.issubset(cols)
        db.close()

    def test_failure_events_signature_unique(self):
        db = _make_db()
        _run_migrations(db)
        db.execute(
            "INSERT INTO failure_events (id, category, signature) "
            "VALUES ('e1', 'lint_error', 'sig-abc')",
        )
        db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO failure_events (id, category, signature) "
                "VALUES ('e2', 'lint_error', 'sig-abc')",
            )
        db.close()

    def test_version_is_2_after_migration(self):
        db = _make_db()
        _run_migrations(db)
        assert _get_current_version(db) == 2
        db.close()
