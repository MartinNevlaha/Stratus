"""SQLite DDL and migration runner for the memory database."""

from __future__ import annotations

import sqlite3

SCHEMA_VERSIONS_DDL = """
CREATE TABLE IF NOT EXISTS schema_versions (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
"""

MEMORY_EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS memory_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'agent',
    scope TEXT NOT NULL DEFAULT 'repo',
    type TEXT NOT NULL DEFAULT 'discovery',
    text TEXT,
    title TEXT,
    tags TEXT NOT NULL DEFAULT '[]',
    refs TEXT NOT NULL DEFAULT '{}',
    ttl TEXT,
    importance REAL NOT NULL DEFAULT 0.5,
    dedupe_key TEXT UNIQUE,
    project TEXT,
    session_id TEXT,
    created_at_epoch INTEGER NOT NULL
);
"""

MEMORY_EVENTS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_memory_events_ts ON memory_events(ts);",
    "CREATE INDEX IF NOT EXISTS idx_memory_events_type ON memory_events(type);",
    "CREATE INDEX IF NOT EXISTS idx_memory_events_project ON memory_events(project);",
    "CREATE INDEX IF NOT EXISTS idx_memory_events_session ON memory_events(session_id);",
    "CREATE INDEX IF NOT EXISTS idx_memory_events_importance ON memory_events(importance);",
    "CREATE INDEX IF NOT EXISTS idx_memory_events_epoch ON memory_events(created_at_epoch);",
]

MEMORY_EVENTS_FTS_DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS memory_events_fts USING fts5(
    title,
    text,
    tags,
    content='memory_events',
    content_rowid='id',
    tokenize='porter unicode61'
);
"""

FTS_TRIGGERS = [
    """
    CREATE TRIGGER IF NOT EXISTS memory_events_ai AFTER INSERT ON memory_events BEGIN
        INSERT INTO memory_events_fts(rowid, title, text, tags)
        VALUES (new.id, new.title, new.text, new.tags);
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS memory_events_ad AFTER DELETE ON memory_events BEGIN
        INSERT INTO memory_events_fts(memory_events_fts, rowid, title, text, tags)
        VALUES ('delete', old.id, old.title, old.text, old.tags);
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS memory_events_au AFTER UPDATE ON memory_events BEGIN
        INSERT INTO memory_events_fts(memory_events_fts, rowid, title, text, tags)
        VALUES ('delete', old.id, old.title, old.text, old.tags);
        INSERT INTO memory_events_fts(rowid, title, text, tags)
        VALUES (new.id, new.title, new.text, new.tags);
    END;
    """,
]

SESSIONS_DDL = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_session_id TEXT NOT NULL,
    project TEXT NOT NULL,
    initial_prompt TEXT,
    started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
"""

MIGRATIONS: dict[int, list[str]] = {
    1: [
        MEMORY_EVENTS_DDL,
        *MEMORY_EVENTS_INDEXES,
        MEMORY_EVENTS_FTS_DDL,
        *FTS_TRIGGERS,
        SESSIONS_DDL,
    ],
}


def get_current_version(db: sqlite3.Connection) -> int:
    try:
        row = db.execute("SELECT MAX(version) FROM schema_versions").fetchone()
        return row[0] or 0
    except sqlite3.OperationalError:
        return 0


def run_migrations(db: sqlite3.Connection) -> None:
    """Apply all pending migrations to the database."""
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")

    db.executescript(SCHEMA_VERSIONS_DDL)

    current = get_current_version(db)

    for version in sorted(MIGRATIONS.keys()):
        if version <= current:
            continue
        for statement in MIGRATIONS[version]:
            db.executescript(statement)
        db.execute("INSERT INTO schema_versions (version) VALUES (?)", (version,))
    db.commit()
