"""LearningDatabase: CRUD for pattern candidates, proposals, and analysis state."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stratus.learning.analytics_db import AnalyticsDB

from stratus.learning.models import (
    CandidateStatus,
    Decision,
    DetectionType,
    LLMAssessment,
    PatternCandidate,
    Proposal,
    ProposalStatus,
)
from stratus.learning.schema import _run_migrations

_DECISION_TO_STATUS = {
    Decision.ACCEPT: ProposalStatus.ACCEPTED,
    Decision.REJECT: ProposalStatus.REJECTED,
    Decision.IGNORE: ProposalStatus.IGNORED,
    Decision.SNOOZE: ProposalStatus.SNOOZED,
}


class LearningDatabase:
    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        _run_migrations(self._conn)

    def close(self) -> None:
        self._conn.close()

    @property
    def analytics(self) -> AnalyticsDB:
        """Lazy-loaded AnalyticsDB sharing this connection."""
        if not hasattr(self, "_analytics"):
            from stratus.learning.analytics_db import AnalyticsDB

            self._analytics = AnalyticsDB(self._conn)
        return self._analytics

    def save_candidate(self, candidate: PatternCandidate) -> str:
        files_json = json.dumps(candidate.files)
        instances_json = json.dumps(candidate.instances)
        assessment_json = (
            candidate.llm_assessment.model_dump_json() if candidate.llm_assessment else None
        )
        self._conn.execute(
            """INSERT OR REPLACE INTO pattern_candidates
               (id, detection_type, count, confidence_raw,
                confidence_final, files, description, instances,
                detected_at, status, llm_assessment, description_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                candidate.id,
                candidate.detection_type,
                candidate.count,
                candidate.confidence_raw,
                candidate.confidence_final,
                files_json,
                candidate.description,
                instances_json,
                candidate.detected_at,
                candidate.status,
                assessment_json,
                candidate.description_hash,
            ),
        )
        self._conn.commit()
        return candidate.id

    def get_candidate(self, cid: str) -> PatternCandidate | None:
        row = self._conn.execute("SELECT * FROM pattern_candidates WHERE id = ?", (cid,)).fetchone()
        return self._row_to_candidate(row) if row else None

    def list_candidates(
        self,
        *,
        status: CandidateStatus | None = None,
        min_confidence: float = 0.0,
        limit: int = 50,
    ) -> list[PatternCandidate]:
        clauses: list[str] = []
        params: list = []
        if status:
            clauses.append("status = ?")
            params.append(status.value)
        if min_confidence > 0.0:
            clauses.append("confidence_final >= ?")
            params.append(min_confidence)
        where = " AND ".join(clauses) if clauses else "1=1"
        params.append(limit)
        rows = self._conn.execute(
            f"SELECT * FROM pattern_candidates WHERE {where}"
            " ORDER BY confidence_final DESC LIMIT ?",
            params,
        ).fetchall()
        return [self._row_to_candidate(r) for r in rows]

    def update_candidate_status(
        self,
        cid: str,
        status: CandidateStatus,
        llm_assessment: LLMAssessment | None = None,
    ) -> None:
        aj = llm_assessment.model_dump_json() if llm_assessment else None
        if aj:
            self._conn.execute(
                "UPDATE pattern_candidates SET status=?, llm_assessment=? WHERE id=?",
                (status.value, aj, cid),
            )
        else:
            self._conn.execute(
                "UPDATE pattern_candidates SET status=? WHERE id=?",
                (status.value, cid),
            )
        self._conn.commit()

    def save_proposal(self, proposal: Proposal) -> str:
        p = proposal
        self._conn.execute(
            """INSERT OR REPLACE INTO proposals
               (id, candidate_id, type, title, description,
                proposed_content, proposed_path, confidence,
                status, presented_at, decided_at, decision,
                edited_content, session_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                p.id,
                p.candidate_id,
                p.type,
                p.title,
                p.description,
                p.proposed_content,
                p.proposed_path,
                p.confidence,
                p.status,
                p.presented_at,
                p.decided_at,
                p.decision,
                p.edited_content,
                p.session_id,
            ),
        )
        self._conn.commit()
        return p.id

    def get_proposal(self, pid: str) -> Proposal | None:
        row = self._conn.execute("SELECT * FROM proposals WHERE id = ?", (pid,)).fetchone()
        return self._row_to_proposal(row) if row else None

    def list_proposals(
        self,
        *,
        status: ProposalStatus | None = None,
        min_confidence: float = 0.0,
        limit: int = 50,
    ) -> list[Proposal]:
        clauses: list[str] = []
        params: list = []
        if status:
            clauses.append("status = ?")
            params.append(status.value)
        if min_confidence > 0.0:
            clauses.append("confidence >= ?")
            params.append(min_confidence)
        where = " AND ".join(clauses) if clauses else "1=1"
        params.append(limit)
        rows = self._conn.execute(
            f"SELECT * FROM proposals WHERE {where} ORDER BY confidence DESC LIMIT ?",
            params,
        ).fetchall()
        return [self._row_to_proposal(r) for r in rows]

    def decide_proposal(
        self,
        pid: str,
        decision: Decision,
        edited_content: str | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        new_status = _DECISION_TO_STATUS[decision]
        self._conn.execute(
            """UPDATE proposals SET status=?, decision=?,
               decided_at=?, edited_content=? WHERE id=?""",
            (new_status.value, decision.value, now, edited_content, pid),
        )
        self._conn.commit()

    def count_session_proposals(self, session_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM proposals WHERE session_id=?",
            (session_id,),
        ).fetchone()
        return row[0]

    def is_in_cooldown(
        self,
        detection_type: DetectionType,
        description_hash: str,
        cooldown_days: int,
    ) -> bool:
        cutoff = (datetime.now(UTC) - timedelta(days=cooldown_days)).isoformat()
        row = self._conn.execute(
            """SELECT COUNT(*) FROM proposals p
               JOIN pattern_candidates c ON p.candidate_id = c.id
               WHERE c.detection_type = ?
                 AND c.description_hash = ?
                 AND p.decision IN ('reject', 'ignore')
                 AND p.decided_at > ?""",
            (detection_type.value, description_hash, cutoff),
        ).fetchone()
        return row[0] > 0

    def get_prior_decision_factor(self, dt: DetectionType) -> float:
        row = self._conn.execute(
            """SELECT
                COALESCE(SUM(CASE WHEN p.decision='accept'
                    THEN 1 ELSE 0 END), 0) as accepts,
                COALESCE(SUM(CASE WHEN p.decision='reject'
                    THEN 1 ELSE 0 END), 0) as rejects
               FROM proposals p
               JOIN pattern_candidates c ON p.candidate_id = c.id
               WHERE c.detection_type = ?""",
            (dt.value,),
        ).fetchone()
        accepts, rejects = row["accepts"], row["rejects"]
        total = accepts + rejects
        if total == 0:
            return 1.0
        return 0.5 + (accepts / total) * 0.5

    def get_db_creation_time(self) -> str | None:
        """Return the applied_at of schema version 1, or None if DB is empty."""
        row = self._conn.execute(
            "SELECT applied_at FROM schema_versions WHERE version = 1"
        ).fetchone()
        return row[0] if row else None

    def get_analysis_state(self) -> dict:
        row = self._conn.execute("SELECT * FROM analysis_state WHERE id = 1").fetchone()
        if row is None:
            return {"last_commit": None, "last_analyzed_at": None, "total_commits_analyzed": 0}
        return {
            "last_commit": row["last_commit"],
            "last_analyzed_at": row["last_analyzed_at"],
            "total_commits_analyzed": row["total_commits_analyzed"],
        }

    def update_analysis_state(self, commit: str, total: int) -> None:
        now = datetime.now(UTC).isoformat()
        self._conn.execute(
            """INSERT INTO analysis_state
               (id, last_commit, last_analyzed_at,
                total_commits_analyzed)
               VALUES (1, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                last_commit=excluded.last_commit,
                last_analyzed_at=excluded.last_analyzed_at,
                total_commits_analyzed=excluded.total_commits_analyzed""",
            (commit, now, total),
        )
        self._conn.commit()

    def stats(self) -> dict:
        ct = self._conn.execute("SELECT COUNT(*) FROM pattern_candidates").fetchone()[0]
        pt = self._conn.execute("SELECT COUNT(*) FROM proposals").fetchone()[0]
        cbs = {
            r["status"]: r["cnt"]
            for r in self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM pattern_candidates GROUP BY status"
            ).fetchall()
        }
        pbs = {
            r["status"]: r["cnt"]
            for r in self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM proposals GROUP BY status"
            ).fetchall()
        }
        return {
            "candidates_total": ct,
            "proposals_total": pt,
            "candidates_by_status": cbs,
            "proposals_by_status": pbs,
        }

    @staticmethod
    def _row_to_candidate(row: sqlite3.Row) -> PatternCandidate:
        llm = None
        if row["llm_assessment"]:
            llm = LLMAssessment.model_validate_json(row["llm_assessment"])
        return PatternCandidate(
            id=row["id"],
            detection_type=row["detection_type"],
            count=row["count"],
            confidence_raw=row["confidence_raw"],
            confidence_final=row["confidence_final"],
            files=json.loads(row["files"]),
            description=row["description"],
            instances=json.loads(row["instances"]),
            detected_at=row["detected_at"],
            status=row["status"],
            llm_assessment=llm,
            description_hash=row["description_hash"],
        )

    @staticmethod
    def _row_to_proposal(row: sqlite3.Row) -> Proposal:
        return Proposal(
            id=row["id"],
            candidate_id=row["candidate_id"],
            type=row["type"],
            title=row["title"],
            description=row["description"],
            proposed_content=row["proposed_content"],
            proposed_path=row["proposed_path"],
            confidence=row["confidence"],
            status=row["status"],
            presented_at=row["presented_at"],
            decided_at=row["decided_at"],
            decision=row["decision"],
            edited_content=row["edited_content"],
            session_id=row["session_id"],
        )
