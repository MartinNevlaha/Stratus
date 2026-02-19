"""Vexor CLI wrapper for semantic code search."""

from __future__ import annotations

import subprocess
import time

from stratus.retrieval.config import VexorConfig
from stratus.retrieval.models import CorpusType, RetrievalResponse, SearchResult


class VexorClient:
    def __init__(self, config: VexorConfig | None = None) -> None:
        self._config = config or VexorConfig()

    def is_available(self) -> bool:
        """Check if vexor binary exists and is runnable."""
        try:
            result = subprocess.run(
                [self._config.binary_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def search(
        self,
        query: str,
        *,
        path: str | None = None,
        top: int = 10,
        mode: str = "hybrid",
        ext: str | None = None,
    ) -> RetrievalResponse:
        """Search indexed codebase via vexor CLI."""
        cmd = [
            self._config.binary_path,
            "search",
            "--format",
            "porcelain",
            "--top",
            str(top),
            "--mode",
            mode,
            query,
        ]
        if path is not None:
            cmd = cmd[:-1] + ["--path", path] + [cmd[-1]]
        if ext is not None:
            cmd = cmd[:-1] + ["--ext", ext] + [cmd[-1]]

        start = time.monotonic()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except FileNotFoundError:
            elapsed = (time.monotonic() - start) * 1000
            return RetrievalResponse(results=[], corpus=CorpusType.CODE, query_time_ms=elapsed)
        except subprocess.TimeoutExpired:
            elapsed = (time.monotonic() - start) * 1000
            return RetrievalResponse(results=[], corpus=CorpusType.CODE, query_time_ms=elapsed)

        elapsed = (time.monotonic() - start) * 1000

        if result.returncode != 0:
            return RetrievalResponse(results=[], corpus=CorpusType.CODE, query_time_ms=elapsed)

        results = self.parse_porcelain(result.stdout)
        return RetrievalResponse(results=results, corpus=CorpusType.CODE, query_time_ms=elapsed)

    def index(
        self,
        *,
        path: str | None = None,
        clear: bool = False,
        mode: str = "full",
    ) -> dict:
        """Trigger vexor indexing."""
        cmd = [self._config.binary_path, "index"]
        if path is not None:
            cmd += ["--path", path]
        if clear:
            cmd += ["--clear"]
        cmd += ["--mode", mode]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except FileNotFoundError:
            return {"status": "error", "message": "vexor binary not found"}
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "indexing timed out"}

        if result.returncode != 0:
            return {"status": "error", "message": result.stderr.strip()}

        return {"status": "ok", "output": result.stdout.strip()}

    @staticmethod
    def parse_porcelain(output: str) -> list[SearchResult]:
        """Parse vexor porcelain output.

        Line format (tab-separated):
        rank score file_path chunk_index line_start line_end heading :: excerpt
        """
        results: list[SearchResult] = []
        for line in output.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t", 6)
            if len(parts) < 7:
                continue
            rank_s, score_s, file_path, chunk_s, line_start_s, line_end_s, heading_excerpt = parts
            # heading :: excerpt — take everything after " :: " as the excerpt
            if " :: " in heading_excerpt:
                _, excerpt = heading_excerpt.split(" :: ", 1)
            else:
                excerpt = heading_excerpt

            results.append(
                SearchResult(
                    rank=int(rank_s),
                    score=float(score_s),
                    file_path=file_path,
                    chunk_index=int(chunk_s),
                    line_start=int(line_start_s),
                    line_end=int(line_end_s),
                    excerpt=excerpt,
                    corpus=CorpusType.CODE,
                )
            )
        return results
