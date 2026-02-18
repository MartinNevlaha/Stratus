"""DevRag MCP client: wraps DevRag server running inside Docker via docker exec subprocess."""

from __future__ import annotations

import json
import subprocess
import time

from stratus.retrieval.config import DevRagConfig
from stratus.retrieval.models import CorpusType, RetrievalResponse, SearchResult

_DOCKER_EXEC_CMD = ["docker", "exec", "-i", "{container}", "node", "/app/dist/stdio.js"]
_INSPECT_TIMEOUT = 5
_EXEC_TIMEOUT = 15


class DevRagClient:
    def __init__(self, config: DevRagConfig | None = None) -> None:
        self._config = config or DevRagConfig()

    def is_available(self) -> bool:
        """Check if the DevRag Docker container is running."""
        try:
            inspect_cmd = [
                "docker", "inspect", "--format", "{{.State.Running}}",
                self._config.container_name,
            ]
            proc = subprocess.run(
                inspect_cmd,
                capture_output=True,
                text=True,
                timeout=_INSPECT_TIMEOUT,
            )
            return proc.stdout.strip() == "true"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def search(self, query: str, *, top_k: int = 10, scope: str | None = None) -> RetrievalResponse:
        """Search governance documents via the DevRag MCP server."""
        params: dict = {"query": query, "top_k": top_k}
        if scope is not None:
            params["scope"] = scope

        start = time.monotonic()
        raw_result = self._call_tool("search", params)
        elapsed_ms = (time.monotonic() - start) * 1000

        raw_items = _extract_text_content(raw_result)
        results = self._parse_search_results(raw_items)
        return RetrievalResponse(
            results=results,
            corpus=CorpusType.GOVERNANCE,
            query_time_ms=elapsed_ms,
        )

    def list_documents(self) -> list[dict]:
        """List all documents indexed by DevRag."""
        raw_result = self._call_tool("list_documents", {})
        return _extract_text_content(raw_result)

    def _call_tool(self, method: str, params: dict) -> dict:
        """Send a JSON-RPC tools/call request via docker exec stdin."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": method, "arguments": params},
        }
        request_str = json.dumps(request)

        cmd = [
            "docker", "exec", "-i",
            self._config.container_name,
            "node", "/app/dist/stdio.js",
        ]

        try:
            proc = subprocess.run(
                cmd,
                input=request_str,
                capture_output=True,
                text=True,
                timeout=_EXEC_TIMEOUT,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("docker not found on PATH") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"DevRag call '{method}' timed out after {_EXEC_TIMEOUT}s") from exc

        if proc.returncode != 0:
            detail = proc.stderr.strip()
            raise RuntimeError(f"DevRag docker exec failed (exit {proc.returncode}): {detail}")

        try:
            response = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON from DevRag: {proc.stdout!r}") from exc

        if "error" in response:
            raise RuntimeError(f"DevRag JSON-RPC error: {response['error']}")

        return response.get("result", {})

    @staticmethod
    def _parse_search_results(raw_results: list[dict]) -> list[SearchResult]:
        """Convert raw DevRag search items to SearchResult models."""
        results: list[SearchResult] = []
        for rank, item in enumerate(raw_results, start=1):
            results.append(
                SearchResult(
                    file_path=item.get("file_path", ""),
                    score=float(item.get("score", 0.0)),
                    rank=rank,
                    excerpt=item.get("content", ""),
                    language=item.get("language"),
                    line_start=item.get("line_start"),
                    line_end=item.get("line_end"),
                    corpus=CorpusType.GOVERNANCE,
                    chunk_index=item.get("chunk_index"),
                )
            )
        return results


def _extract_text_content(result: dict) -> list[dict]:
    """Parse the nested content list from a JSON-RPC result, return decoded list."""
    content = result.get("content", [])
    for block in content:
        if block.get("type") == "text":
            try:
                return json.loads(block["text"])
            except (json.JSONDecodeError, KeyError):
                return []
    return []
