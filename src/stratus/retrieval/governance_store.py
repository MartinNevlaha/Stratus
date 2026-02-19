"""SQLite+FTS5 governance document indexer for rules, ADRs, templates, skills, agents."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from pathlib import Path

SCHEMA_VERSIONS_DDL = """
CREATE TABLE IF NOT EXISTS schema_versions (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
"""

GOVERNANCE_DOCS_DDL = """
CREATE TABLE IF NOT EXISTS governance_docs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    title TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    indexed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(file_path, chunk_index)
);
"""

GOVERNANCE_FTS_DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS governance_fts USING fts5(
    title, content, doc_type,
    content='governance_docs', content_rowid='id',
    tokenize='porter unicode61'
);
"""

FTS_TRIGGERS = [
    """
    CREATE TRIGGER IF NOT EXISTS governance_docs_ai AFTER INSERT ON governance_docs BEGIN
        INSERT INTO governance_fts(rowid, title, content, doc_type)
        VALUES (new.id, new.title, new.content, new.doc_type);
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS governance_docs_ad AFTER DELETE ON governance_docs BEGIN
        INSERT INTO governance_fts(governance_fts, rowid, title, content, doc_type)
        VALUES ('delete', old.id, old.title, old.content, old.doc_type);
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS governance_docs_au AFTER UPDATE ON governance_docs BEGIN
        INSERT INTO governance_fts(governance_fts, rowid, title, content, doc_type)
        VALUES ('delete', old.id, old.title, old.content, old.doc_type);
        INSERT INTO governance_fts(rowid, title, content, doc_type)
        VALUES (new.id, new.title, new.content, new.doc_type);
    END;
    """,
]

MIGRATIONS: dict[int, list[str]] = {
    1: [
        GOVERNANCE_DOCS_DDL,
        GOVERNANCE_FTS_DDL,
        *FTS_TRIGGERS,
    ],
    2: [
        # Clear old relative-path records — they are ambiguous across projects.
        "DELETE FROM governance_docs;",
    ],
}

# Governance doc patterns: (glob_pattern, doc_type)
_DOC_PATTERNS: list[tuple[str, str]] = [
    (".claude/rules/*.md", "rule"),
    ("docs/decisions/*.md", "adr"),
    (".claude/templates/*.md", "template"),
    (".claude/skills/**/*.md", "skill"),
    (".claude/agents/*.md", "agent"),
    ("docs/architecture/*.md", "architecture"),
    ("**/CLAUDE.md", "project"),
    ("**/README.md", "project"),
]

# Directories to skip during recursive glob (noise, build artifacts, deps)
_SKIP_DIRS: frozenset[str] = frozenset({
    "node_modules", ".git", ".venv", "venv", "__pycache__",
    "dist", "build", ".next", "out", "target", ".gradle",
    "vendor", "coverage", ".cache", ".tox", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", ".worktrees",
})

_H2_SPLIT = re.compile(r"^## ", re.MULTILINE)


def _chunk_markdown(text: str, fallback_title: str = "") -> list[dict]:
    """Split markdown by ## headers into chunks. Returns list of {title, content}."""
    if not text.strip():
        return []

    parts = _H2_SPLIT.split(text)
    chunks: list[dict] = []

    # Content before the first ## header
    if parts[0].strip():
        chunks.append({"title": fallback_title, "content": parts[0].strip()})

    # Each part after split starts with the header text (## was removed by split)
    for part in parts[1:]:
        lines = part.split("\n", 1)
        title = lines[0].strip()
        content = lines[1].strip() if len(lines) > 1 else ""
        if not content:
            continue
        chunks.append({"title": title, "content": content})

    return chunks


def _file_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _run_migrations(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_VERSIONS_DDL)

    try:
        row = conn.execute("SELECT MAX(version) FROM schema_versions").fetchone()
        current = row[0] or 0
    except sqlite3.OperationalError:
        current = 0

    for version in sorted(MIGRATIONS.keys()):
        if version <= current:
            continue
        for statement in MIGRATIONS[version]:
            conn.executescript(statement)
        conn.execute("INSERT INTO schema_versions (version) VALUES (?)", (version,))
    conn.commit()


class GovernanceStore:
    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        _run_migrations(self._conn)

    def close(self) -> None:
        self._conn.close()

    def index_project(self, project_root: str) -> dict:
        """Scan governance doc locations, index new/changed files, remove stale entries."""
        root = Path(project_root)
        files_indexed = 0
        files_skipped = 0
        files_removed = 0
        chunks_indexed = 0

        # Collect all governance files with their doc_type, keyed by absolute path
        found_files: dict[str, str] = {}  # abs_path_str -> doc_type
        for pattern, doc_type in _DOC_PATTERNS:
            for fp in root.glob(pattern):
                if fp.is_file() and fp.suffix == ".md" and not fp.is_symlink():
                    rel_parts = fp.relative_to(root).parts
                    if any(part in _SKIP_DIRS for part in rel_parts):
                        continue
                    found_files[str(fp.resolve())] = doc_type

        # Get existing file hashes for this project root only
        existing = {}
        for row in self._conn.execute(
            "SELECT DISTINCT file_path, file_hash FROM governance_docs WHERE file_path LIKE ?",
            (str(root.resolve()) + "%",),
        ).fetchall():
            existing[row["file_path"]] = row["file_hash"]

        try:
            # Index new/changed files
            for abs_path_str, doc_type in found_files.items():
                content = Path(abs_path_str).read_text()
                new_hash = _file_hash(content)

                if abs_path_str in existing and existing[abs_path_str] == new_hash:
                    files_skipped += 1
                    continue

                # Delete old chunks for this file
                self._conn.execute(
                    "DELETE FROM governance_docs WHERE file_path = ?", (abs_path_str,)
                )

                # Chunk and insert
                fallback_title = Path(abs_path_str).name
                file_chunks = _chunk_markdown(content, fallback_title=fallback_title)
                for idx, chunk in enumerate(file_chunks):
                    self._conn.execute(
                        """INSERT INTO governance_docs
                           (file_path, chunk_index, title, content, doc_type, file_hash)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (abs_path_str, idx, chunk["title"], chunk["content"], doc_type, new_hash),
                    )
                    chunks_indexed += 1
                files_indexed += 1

            # Remove stale entries (files no longer on disk)
            for abs_path_str in existing:
                if abs_path_str not in found_files:
                    self._conn.execute(
                        "DELETE FROM governance_docs WHERE file_path = ?", (abs_path_str,)
                    )
                    files_removed += 1

            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

        return {
            "files_indexed": files_indexed,
            "files_skipped": files_skipped,
            "files_removed": files_removed,
            "chunks_indexed": chunks_indexed,
        }

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        doc_type: str | None = None,
        project_root: str | None = None,
    ) -> list[dict]:
        """FTS5 search with bm25 scoring. Optional doc_type and project_root filters."""
        if not query.strip():
            return []

        params: list = [query]
        where_clauses = ["governance_fts MATCH ?"]
        if doc_type:
            where_clauses.append("g.doc_type = ?")
            params.append(doc_type)
        if project_root:
            where_clauses.append("g.file_path LIKE ?")
            params.append(str(Path(project_root).resolve()) + "%")
        params.append(top_k)

        where_str = " AND ".join(where_clauses)
        rows = self._conn.execute(
            f"""SELECT g.file_path, g.title, g.content, g.doc_type, g.chunk_index,
                       bm25(governance_fts) AS score
                FROM governance_docs g
                JOIN governance_fts ON governance_fts.rowid = g.id
                WHERE {where_str}
                ORDER BY score
                LIMIT ?""",
            params,
        ).fetchall()

        return [
            {
                "file_path": r["file_path"],
                "title": r["title"],
                "content": r["content"],
                "doc_type": r["doc_type"],
                "chunk_index": r["chunk_index"],
                "score": r["score"],
            }
            for r in rows
        ]

    def list_documents(self) -> list[dict]:
        """List all unique indexed files with their doc_type."""
        rows = self._conn.execute(
            """SELECT DISTINCT file_path, doc_type
               FROM governance_docs
               ORDER BY file_path"""
        ).fetchall()
        return [{"file_path": r["file_path"], "doc_type": r["doc_type"]} for r in rows]

    def stats(self, *, project_root: str | None = None) -> dict:
        """Return document and chunk counts with doc_type breakdown.

        Pass project_root to filter counts to a single project; omit for all projects.
        """
        where = ""
        params: list = []
        if project_root:
            where = "WHERE file_path LIKE ?"
            params.append(str(Path(project_root).resolve()) + "%")

        total_files = self._conn.execute(
            f"SELECT COUNT(DISTINCT file_path) FROM governance_docs {where}", params
        ).fetchone()[0]
        total_chunks = self._conn.execute(
            f"SELECT COUNT(*) FROM governance_docs {where}", params
        ).fetchone()[0]
        type_rows = self._conn.execute(
            f"SELECT doc_type, COUNT(DISTINCT file_path) as cnt "
            f"FROM governance_docs {where} GROUP BY doc_type",
            params,
        ).fetchall()
        by_doc_type = {r["doc_type"]: r["cnt"] for r in type_rows}
        return {
            "total_files": total_files,
            "total_chunks": total_chunks,
            "by_doc_type": by_doc_type,
        }
