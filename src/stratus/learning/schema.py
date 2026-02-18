"""SQLite DDL and migration runner for the learning database."""

from __future__ import annotations

import sqlite3

SCHEMA_VERSIONS_DDL = """
CREATE TABLE IF NOT EXISTS schema_versions (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
"""

PATTERN_CANDIDATES_DDL = """
CREATE TABLE IF NOT EXISTS pattern_candidates (
    id TEXT PRIMARY KEY,
    detection_type TEXT NOT NULL,
    count INTEGER NOT NULL,
    confidence_raw REAL NOT NULL,
    confidence_final REAL NOT NULL,
    files TEXT NOT NULL DEFAULT '[]',
    description TEXT NOT NULL,
    instances TEXT NOT NULL DEFAULT '[]',
    detected_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    status TEXT NOT NULL DEFAULT 'pending',
    llm_assessment TEXT,
    description_hash TEXT
);
"""

PATTERN_CANDIDATES_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_pc_status ON pattern_candidates(status);",
    "CREATE INDEX IF NOT EXISTS idx_pc_type ON pattern_candidates(detection_type);",
    "CREATE INDEX IF NOT EXISTS idx_pc_confidence ON pattern_candidates(confidence_final);",
    "CREATE INDEX IF NOT EXISTS idx_pc_hash ON pattern_candidates(description_hash);",
]

PROPOSALS_DDL = """
CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    proposed_content TEXT NOT NULL,
    proposed_path TEXT,
    confidence REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    presented_at TEXT,
    decided_at TEXT,
    decision TEXT,
    edited_content TEXT,
    session_id TEXT
);
"""

PROPOSALS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_prop_status ON proposals(status);",
    "CREATE INDEX IF NOT EXISTS idx_prop_candidate ON proposals(candidate_id);",
    "CREATE INDEX IF NOT EXISTS idx_prop_session ON proposals(session_id);",
    "CREATE INDEX IF NOT EXISTS idx_prop_confidence ON proposals(confidence);",
]

ANALYSIS_STATE_DDL = """
CREATE TABLE IF NOT EXISTS analysis_state (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    last_commit TEXT,
    last_analyzed_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    total_commits_analyzed INTEGER NOT NULL DEFAULT 0
);
"""

FAILURE_EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS failure_events (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    file_path TEXT,
    detail TEXT NOT NULL DEFAULT '',
    session_id TEXT,
    recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    signature TEXT NOT NULL DEFAULT ''
);
"""

FAILURE_EVENTS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_fe_category ON failure_events(category);",
    "CREATE INDEX IF NOT EXISTS idx_fe_file_path ON failure_events(file_path);",
    "CREATE INDEX IF NOT EXISTS idx_fe_recorded_at ON failure_events(recorded_at);",
    "CREATE INDEX IF NOT EXISTS idx_fe_session_id ON failure_events(session_id);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_fe_signature ON failure_events(signature);",
]

RULE_BASELINES_DDL = """
CREATE TABLE IF NOT EXISTS rule_baselines (
    id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    rule_path TEXT NOT NULL,
    category TEXT NOT NULL,
    baseline_count INTEGER NOT NULL DEFAULT 0,
    baseline_window_days INTEGER NOT NULL DEFAULT 30,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    category_source TEXT NOT NULL DEFAULT 'heuristic'
);
"""

RULE_BASELINES_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_rb_proposal ON rule_baselines(proposal_id);",
    "CREATE INDEX IF NOT EXISTS idx_rb_category ON rule_baselines(category);",
]

MIGRATIONS: dict[int, list[str]] = {
    1: [
        PATTERN_CANDIDATES_DDL,
        *PATTERN_CANDIDATES_INDEXES,
        PROPOSALS_DDL,
        *PROPOSALS_INDEXES,
        ANALYSIS_STATE_DDL,
    ],
    2: [
        FAILURE_EVENTS_DDL,
        *FAILURE_EVENTS_INDEXES,
        RULE_BASELINES_DDL,
        *RULE_BASELINES_INDEXES,
    ],
}


def _get_current_version(db: sqlite3.Connection) -> int:
    try:
        row = db.execute("SELECT MAX(version) FROM schema_versions").fetchone()
        return row[0] or 0
    except sqlite3.OperationalError:
        return 0


def _run_migrations(db: sqlite3.Connection) -> None:
    """Apply all pending migrations to the learning database."""
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA_VERSIONS_DDL)

    current = _get_current_version(db)
    for version in sorted(MIGRATIONS.keys()):
        if version <= current:
            continue
        for statement in MIGRATIONS[version]:
            db.executescript(statement)
        db.execute("INSERT INTO schema_versions (version) VALUES (?)", (version,))
    db.commit()
