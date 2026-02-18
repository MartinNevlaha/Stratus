"""Analytics CRUD — failure events and rule baselines."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from stratus.learning.models import (
    FailureCategory,
    FailureEvent,
    FailureTrend,
    FileHotspot,
    RuleBaseline,
)


class AnalyticsDB:
    """Failure event and rule baseline CRUD, sharing a sqlite3.Connection."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def record_failure(self, event: FailureEvent) -> str:
        """Record a failure event. Dedup via INSERT OR IGNORE on signature."""
        self._conn.execute(
            """INSERT OR IGNORE INTO failure_events
               (id, category, file_path, detail, session_id, recorded_at, signature)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                event.id, event.category, event.file_path, event.detail,
                event.session_id, event.recorded_at, event.signature,
            ),
        )
        self._conn.commit()
        return event.id

    def count_failures(
        self,
        category: FailureCategory | None = None,
        *,
        since: str | None = None,
        until: str | None = None,
        file_path: str | None = None,
    ) -> int:
        clauses: list[str] = []
        params: list = []
        if category is not None:
            clauses.append("category = ?")
            params.append(category.value)
        if since is not None:
            clauses.append("recorded_at >= ?")
            params.append(since)
        if until is not None:
            clauses.append("recorded_at <= ?")
            params.append(until)
        if file_path is not None:
            clauses.append("file_path = ?")
            params.append(file_path)
        where = " AND ".join(clauses) if clauses else "1=1"
        row = self._conn.execute(
            f"SELECT COUNT(*) FROM failure_events WHERE {where}", params,
        ).fetchone()
        return row[0]

    def list_failures(
        self,
        category: FailureCategory | None = None,
        *,
        limit: int = 50,
        since: str | None = None,
    ) -> list[FailureEvent]:
        clauses: list[str] = []
        params: list = []
        if category is not None:
            clauses.append("category = ?")
            params.append(category.value)
        if since is not None:
            clauses.append("recorded_at >= ?")
            params.append(since)
        where = " AND ".join(clauses) if clauses else "1=1"
        params.append(limit)
        rows = self._conn.execute(
            f"SELECT * FROM failure_events WHERE {where}"
            " ORDER BY recorded_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [self._row_to_failure(r) for r in rows]

    def failure_trends(
        self,
        category: FailureCategory | None = None,
        *,
        days: int = 30,
    ) -> list[FailureTrend]:
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        clauses: list[str] = ["recorded_at >= ?"]
        params: list = [cutoff]
        if category is not None:
            clauses.append("category = ?")
            params.append(category.value)
        where = " AND ".join(clauses)
        rows = self._conn.execute(
            f"""SELECT date(recorded_at) as period, category, COUNT(*) as cnt
                FROM failure_events WHERE {where}
                GROUP BY period, category ORDER BY period""",
            params,
        ).fetchall()
        return [
            FailureTrend(
                category=FailureCategory(r["category"]),
                period=r["period"],
                count=r["cnt"],
            )
            for r in rows
        ]

    def file_hotspots(
        self,
        *,
        limit: int = 10,
        since: str | None = None,
    ) -> list[FileHotspot]:
        clauses: list[str] = ["file_path IS NOT NULL"]
        params: list = []
        if since is not None:
            clauses.append("recorded_at >= ?")
            params.append(since)
        where = " AND ".join(clauses)
        params.append(limit)
        rows = self._conn.execute(
            f"""SELECT file_path, COUNT(*) as total,
                       GROUP_CONCAT(category) as cats
                FROM failure_events WHERE {where}
                GROUP BY file_path
                ORDER BY total DESC LIMIT ?""",
            params,
        ).fetchall()
        result = []
        for r in rows:
            cats = r["cats"].split(",") if r["cats"] else []
            by_cat: dict[str, int] = {}
            for c in cats:
                by_cat[c] = by_cat.get(c, 0) + 1
            result.append(FileHotspot(
                file_path=r["file_path"],
                total_failures=r["total"],
                by_category=by_cat,
            ))
        return result

    def save_baseline(self, baseline: RuleBaseline) -> None:
        self._conn.execute(
            """INSERT INTO rule_baselines
               (id, proposal_id, rule_path, category, baseline_count,
                baseline_window_days, created_at, category_source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                baseline.id, baseline.proposal_id, baseline.rule_path,
                baseline.category, baseline.baseline_count,
                baseline.baseline_window_days, baseline.created_at,
                baseline.category_source,
            ),
        )
        self._conn.commit()

    def get_baseline(self, baseline_id: str) -> RuleBaseline | None:
        row = self._conn.execute(
            "SELECT * FROM rule_baselines WHERE id = ?", (baseline_id,),
        ).fetchone()
        return self._row_to_baseline(row) if row else None

    def list_baselines(self) -> list[RuleBaseline]:
        rows = self._conn.execute(
            "SELECT * FROM rule_baselines ORDER BY created_at DESC"
        ).fetchall()
        return [self._row_to_baseline(r) for r in rows]

    @staticmethod
    def _row_to_failure(row: sqlite3.Row) -> FailureEvent:
        return FailureEvent(
            id=row["id"],
            category=row["category"],
            file_path=row["file_path"],
            detail=row["detail"],
            session_id=row["session_id"],
            recorded_at=row["recorded_at"],
            signature=row["signature"],
        )

    @staticmethod
    def _row_to_baseline(row: sqlite3.Row) -> RuleBaseline:
        return RuleBaseline(
            id=row["id"],
            proposal_id=row["proposal_id"],
            rule_path=row["rule_path"],
            category=row["category"],
            baseline_count=row["baseline_count"],
            baseline_window_days=row["baseline_window_days"],
            created_at=row["created_at"],
            category_source=row["category_source"],
        )
