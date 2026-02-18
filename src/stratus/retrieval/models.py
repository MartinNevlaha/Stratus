"""Pydantic models for the retrieval layer."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class CorpusType(StrEnum):
    CODE = "code"
    GOVERNANCE = "governance"


class SearchResult(BaseModel):
    file_path: str
    score: float
    rank: int
    excerpt: str
    language: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    corpus: CorpusType | None = None
    chunk_index: int | None = None


class RetrievalResponse(BaseModel):
    results: list[SearchResult]
    corpus: CorpusType
    query_time_ms: float
    total_indexed: int | None = None


class IndexStatus(BaseModel):
    last_indexed_commit: str | None = None
    last_indexed_at: str | None = None
    total_files: int = 0
    model: str | None = None
    stale: bool = True
