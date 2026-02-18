"""Database class for memory event CRUD and FTS5 search."""

from __future__ import annotations

import json
import sqlite3

from stratus.memory.models import MemoryEvent, Session
from stratus.memory.schema import run_migrations


class Database:
    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        run_migrations(self._conn)

    def close(self) -> None:
        self._conn.close()

    def save_event(self, event: MemoryEvent) -> int:
        """Insert or upsert (on dedupe_key conflict) a memory event. Returns row id."""
        tags_json = json.dumps(event.tags)
        refs_json = json.dumps(event.refs)

        if event.dedupe_key:
            cursor = self._conn.execute(
                """INSERT INTO memory_events
                   (ts, actor, scope, type, text, title, tags, refs, ttl,
                    importance, dedupe_key, project, session_id, created_at_epoch)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(dedupe_key) DO UPDATE SET
                    ts=excluded.ts, text=excluded.text, title=excluded.title,
                    tags=excluded.tags, refs=excluded.refs, importance=excluded.importance
                   RETURNING id""",
                (
                    event.ts,
                    event.actor,
                    event.scope,
                    event.type,
                    event.text,
                    event.title,
                    tags_json,
                    refs_json,
                    event.ttl,
                    event.importance,
                    event.dedupe_key,
                    event.project,
                    event.session_id,
                    event.created_at_epoch,
                ),
            )
        else:
            cursor = self._conn.execute(
                """INSERT INTO memory_events
                   (ts, actor, scope, type, text, title, tags, refs, ttl,
                    importance, dedupe_key, project, session_id, created_at_epoch)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   RETURNING id""",
                (
                    event.ts,
                    event.actor,
                    event.scope,
                    event.type,
                    event.text,
                    event.title,
                    tags_json,
                    refs_json,
                    event.ttl,
                    event.importance,
                    event.dedupe_key,
                    event.project,
                    event.session_id,
                    event.created_at_epoch,
                ),
            )
        row_id = cursor.fetchone()[0]
        self._conn.commit()
        return row_id

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        type: str | None = None,
        scope: str | None = None,
        project: str | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
        offset: int = 0,
    ) -> list[MemoryEvent]:
        """Full-text search over memory events using FTS5."""
        params: list = []
        where_clauses = []

        # FTS5 match
        fts_clause = (
            "me.id IN (SELECT rowid FROM memory_events_fts WHERE memory_events_fts MATCH ?)"
        )
        where_clauses.append(fts_clause)
        params.append(query)

        if type:
            where_clauses.append("me.type = ?")
            params.append(type)
        if scope:
            where_clauses.append("me.scope = ?")
            params.append(scope)
        if project:
            where_clauses.append("me.project = ?")
            params.append(project)
        if date_start:
            where_clauses.append("me.ts >= ?")
            params.append(date_start)
        if date_end:
            where_clauses.append("me.ts <= ?")
            params.append(date_end)

        where_sql = " AND ".join(where_clauses)
        sql = f"""
            SELECT me.* FROM memory_events me
            WHERE {where_sql}
            ORDER BY me.ts DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_event(row) for row in rows]

    def timeline(
        self,
        anchor_id: int,
        depth_before: int = 10,
        depth_after: int = 10,
        project: str | None = None,
    ) -> list[MemoryEvent]:
        """Get chronological context around an anchor event."""
        # Get the anchor event's timestamp
        anchor_row = self._conn.execute(
            "SELECT ts FROM memory_events WHERE id = ?", (anchor_id,)
        ).fetchone()
        if not anchor_row:
            return []

        anchor_ts = anchor_row["ts"]
        project_clause = " AND project = ?" if project else ""
        project_params: list = [project] if project else []

        # Events before anchor (ordered ascending)
        before_sql = f"""
            SELECT * FROM memory_events
            WHERE ts < ? {project_clause}
            ORDER BY ts DESC LIMIT ?
        """
        before_rows = self._conn.execute(
            before_sql, [anchor_ts, *project_params, depth_before]
        ).fetchall()

        # Anchor itself
        anchor_sql = f"""
            SELECT * FROM memory_events WHERE id = ? {project_clause}
        """
        anchor_rows = self._conn.execute(anchor_sql, [anchor_id, *project_params]).fetchall()

        # Events after anchor
        after_sql = f"""
            SELECT * FROM memory_events
            WHERE ts > ? {project_clause}
            ORDER BY ts ASC LIMIT ?
        """
        after_rows = self._conn.execute(
            after_sql, [anchor_ts, *project_params, depth_after]
        ).fetchall()

        # Combine: before (reversed to ascending) + anchor + after
        all_rows = list(reversed(before_rows)) + list(anchor_rows) + list(after_rows)
        return [self._row_to_event(row) for row in all_rows]

    def get_events(self, ids: list[int]) -> list[MemoryEvent]:
        """Batch fetch events by IDs."""
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        rows = self._conn.execute(
            f"SELECT * FROM memory_events WHERE id IN ({placeholders})", ids
        ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def init_session(
        self,
        content_session_id: str,
        project: str,
        prompt: str | None = None,
    ) -> Session:
        """Create a new session record."""
        cursor = self._conn.execute(
            """INSERT INTO sessions (content_session_id, project, initial_prompt)
               VALUES (?, ?, ?) RETURNING id, started_at""",
            (content_session_id, project, prompt),
        )
        row = cursor.fetchone()
        self._conn.commit()
        return Session(
            id=row["id"],
            content_session_id=content_session_id,
            project=project,
            initial_prompt=prompt,
            started_at=row["started_at"],
        )

    def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Session]:
        rows = self._conn.execute(
            "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [
            Session(
                id=row["id"],
                content_session_id=row["content_session_id"],
                project=row["project"],
                initial_prompt=row["initial_prompt"],
                started_at=row["started_at"],
            )
            for row in rows
        ]

    def recent_events(
        self,
        *,
        project: str | None = None,
        limit: int = 10,
    ) -> list[MemoryEvent]:
        """Fetch recent events without FTS, ordered by timestamp descending."""
        if project:
            rows = self._conn.execute(
                "SELECT * FROM memory_events WHERE project = ? ORDER BY ts DESC LIMIT ?",
                (project, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM memory_events ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def get_stats(self) -> dict:
        total_events = self._conn.execute("SELECT COUNT(*) FROM memory_events").fetchone()[0]
        total_sessions = self._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]

        type_rows = self._conn.execute(
            "SELECT type, COUNT(*) as cnt FROM memory_events GROUP BY type"
        ).fetchall()
        events_by_type = {row["type"]: row["cnt"] for row in type_rows}

        return {
            "total_events": total_events,
            "total_sessions": total_sessions,
            "events_by_type": events_by_type,
        }

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> MemoryEvent:
        return MemoryEvent(
            id=row["id"],
            ts=row["ts"],
            actor=row["actor"],
            scope=row["scope"],
            type=row["type"],
            text=row["text"],
            title=row["title"],
            tags=json.loads(row["tags"]),
            refs=json.loads(row["refs"]),
            ttl=row["ttl"],
            importance=row["importance"],
            dedupe_key=row["dedupe_key"],
            project=row["project"],
            session_id=row["session_id"],
            created_at_epoch=row["created_at_epoch"],
        )
