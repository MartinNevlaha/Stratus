"""SQLite cache for embedding results, following memory/database.py pattern."""

from __future__ import annotations

import hashlib
import sqlite3

SCHEMA_VERSIONS_DDL = """
CREATE TABLE IF NOT EXISTS schema_versions (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
"""

EMBED_CACHE_DDL = """
CREATE TABLE IF NOT EXISTS embed_cache (
    content_hash TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    model_name TEXT NOT NULL,
    cached_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    hit_count INTEGER NOT NULL DEFAULT 0
);
"""

EMBED_CACHE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_embed_cache_file ON embed_cache(file_path);",
    "CREATE INDEX IF NOT EXISTS idx_embed_cache_model ON embed_cache(model_name);",
]

MIGRATIONS: dict[int, list[str]] = {
    1: [
        EMBED_CACHE_DDL,
        *EMBED_CACHE_INDEXES,
    ],
}


def _get_current_version(db: sqlite3.Connection) -> int:
    try:
        row = db.execute("SELECT MAX(version) FROM schema_versions").fetchone()
        return row[0] or 0
    except sqlite3.OperationalError:
        return 0


def _run_migrations(db: sqlite3.Connection) -> None:
    """Apply all pending migrations to the embed cache database."""
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


def compute_content_hash(content: str, model_name: str) -> str:
    """SHA256 hex of content + model_name."""
    payload = f"{model_name}:{content}"
    return hashlib.sha256(payload.encode()).hexdigest()


class EmbedCache:
    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        _run_migrations(self._conn)

    def close(self) -> None:
        self._conn.close()

    def has(self, content_hash: str) -> bool:
        """Return True if content_hash exists in the cache."""
        row = self._conn.execute(
            "SELECT 1 FROM embed_cache WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        return row is not None

    def get(self, content_hash: str) -> dict | None:
        """Return row as dict and increment hit_count, or None if not found."""
        self._conn.execute(
            "UPDATE embed_cache SET hit_count = hit_count + 1 WHERE content_hash = ?",
            (content_hash,),
        )
        self._conn.commit()

        row = self._conn.execute(
            "SELECT * FROM embed_cache WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def put(
        self,
        content_hash: str,
        file_path: str,
        chunk_index: int,
        model_name: str,
    ) -> None:
        """Insert or replace a cache entry."""
        self._conn.execute(
            """INSERT OR REPLACE INTO embed_cache
               (content_hash, file_path, chunk_index, model_name)
               VALUES (?, ?, ?, ?)""",
            (content_hash, file_path, chunk_index, model_name),
        )
        self._conn.commit()

    def invalidate(self, file_path: str) -> int:
        """Delete all entries for file_path. Returns count of deleted rows."""
        cursor = self._conn.execute(
            "DELETE FROM embed_cache WHERE file_path = ?", (file_path,)
        )
        self._conn.commit()
        return cursor.rowcount

    def stats(self) -> dict:
        """Return total_entries, total_hits, and list of distinct models."""
        total_entries = self._conn.execute(
            "SELECT COUNT(*) FROM embed_cache"
        ).fetchone()[0]

        total_hits = self._conn.execute(
            "SELECT COALESCE(SUM(hit_count), 0) FROM embed_cache"
        ).fetchone()[0]

        model_rows = self._conn.execute(
            "SELECT DISTINCT model_name FROM embed_cache ORDER BY model_name"
        ).fetchall()
        models = [row[0] for row in model_rows]

        return {
            "total_entries": total_entries,
            "total_hits": total_hits,
            "models": models,
        }

    def prune(self, older_than_days: int = 30) -> int:
        """Delete entries older than older_than_days. Returns count of deleted rows."""
        cursor = self._conn.execute(
            """DELETE FROM embed_cache
               WHERE cached_at < strftime('%Y-%m-%dT%H:%M:%fZ', 'now', ? || ' days')""",
            (f"-{older_than_days}",),
        )
        self._conn.commit()
        return cursor.rowcount
