"""Tests for DevRag MCP client (docker exec subprocess wrapper)."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from stratus.retrieval.config import DevRagConfig
from stratus.retrieval.devrag import DevRagClient
from stratus.retrieval.models import CorpusType, RetrievalResponse, SearchResult


def _make_proc(stdout: str = "", returncode: int = 0, stderr: str = "") -> MagicMock:
    proc = MagicMock()
    proc.stdout = stdout
    proc.returncode = returncode
    proc.stderr = stderr
    return proc


def _jsonrpc_response(result: dict) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": 1, "result": result})


def _search_content(items: list[dict]) -> str:
    return _jsonrpc_response({"content": [{"type": "text", "text": json.dumps(items)}]})


class TestDevRagClient:
    def test_is_available_when_container_running(self):
        client = DevRagClient()
        with patch("stratus.retrieval.devrag.subprocess.run") as mock_run:
            mock_run.return_value = _make_proc(stdout="true\n")
            assert client.is_available() is True
        mock_run.assert_called_once_with(
            ["docker", "inspect", "--format", "{{.State.Running}}", "devrag"],
            capture_output=True,
            text=True,
            timeout=5,
        )

    def test_is_available_when_container_stopped(self):
        client = DevRagClient()
        with patch("stratus.retrieval.devrag.subprocess.run") as mock_run:
            mock_run.return_value = _make_proc(stdout="false\n")
            assert client.is_available() is False

    def test_is_available_when_docker_missing(self):
        client = DevRagClient()
        with patch("stratus.retrieval.devrag.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("docker not found")
            assert client.is_available() is False

    def test_search_returns_retrieval_response(self):
        client = DevRagClient()
        raw_items = [
            {"file_path": "docs/api.md", "content": "API documentation...", "score": 0.92},
        ]
        response_json = _search_content(raw_items)
        with patch.object(client, "_call_tool", return_value=json.loads(response_json)["result"]):
            result = client.search("authentication")
        assert isinstance(result, RetrievalResponse)
        assert result.corpus == CorpusType.GOVERNANCE
        assert len(result.results) == 1
        assert result.results[0].file_path == "docs/api.md"
        assert result.results[0].score == 0.92
        assert result.query_time_ms >= 0

    def test_search_with_scope_parameter(self):
        client = DevRagClient()
        raw_items = [{"file_path": "docs/auth.md", "content": "Auth details", "score": 0.88}]
        response_json = _search_content(raw_items)
        captured: list[dict] = []

        def fake_call_tool(method: str, params: dict) -> dict:
            captured.append({"method": method, "params": params})
            return json.loads(response_json)["result"]

        with patch.object(client, "_call_tool", side_effect=fake_call_tool):
            client.search("login", top_k=5, scope="docs/")

        assert captured[0]["params"]["top_k"] == 5
        assert captured[0]["params"]["scope"] == "docs/"

    def test_search_handles_timeout(self):
        client = DevRagClient()
        with patch("stratus.retrieval.devrag.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker", timeout=15)
            with pytest.raises(RuntimeError, match="timed out"):
                client.search("something")

    def test_search_handles_docker_error(self):
        client = DevRagClient()
        with patch("stratus.retrieval.devrag.subprocess.run") as mock_run:
            mock_run.return_value = _make_proc(
                stdout="", returncode=1, stderr="Error: container not found"
            )
            with pytest.raises(RuntimeError, match="DevRag"):
                client.search("something")

    def test_list_documents_success(self):
        client = DevRagClient()
        docs = [
            {"file_path": "docs/intro.md", "size": 1024},
            {"file_path": "docs/api.md", "size": 2048},
        ]
        mock_result = {"content": [{"type": "text", "text": json.dumps(docs)}]}
        with patch.object(client, "_call_tool", return_value=mock_result):
            result = client.list_documents()
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["file_path"] == "docs/intro.md"

    def test_call_tool_builds_correct_jsonrpc(self):
        client = DevRagClient(DevRagConfig(container_name="mydevrag"))
        items = [{"file_path": "a.md", "content": "hello", "score": 0.9}]
        response_payload = _search_content(items)
        with patch("stratus.retrieval.devrag.subprocess.run") as mock_run:
            mock_run.return_value = _make_proc(stdout=response_payload)
            client._call_tool("search", {"query": "auth", "top_k": 3})

        call_kwargs = mock_run.call_args
        cmd = call_kwargs[0][0]
        assert cmd[0] == "docker"
        assert cmd[3] == "mydevrag"

        stdin_data = json.loads(call_kwargs[1]["input"])
        assert stdin_data["jsonrpc"] == "2.0"
        assert stdin_data["method"] == "tools/call"
        assert stdin_data["params"]["name"] == "search"
        assert stdin_data["params"]["arguments"] == {"query": "auth", "top_k": 3}

    def test_call_tool_handles_invalid_json_response(self):
        client = DevRagClient()
        with patch("stratus.retrieval.devrag.subprocess.run") as mock_run:
            mock_run.return_value = _make_proc(stdout="not valid json")
            with pytest.raises(RuntimeError, match="Invalid JSON"):
                client._call_tool("search", {"query": "x"})


class TestParseSearchResults:
    def test_parse_search_results_basic(self):
        raw = [
            {"file_path": "docs/api.md", "content": "API documentation...", "score": 0.92},
            {"file_path": "docs/auth.md", "content": "Auth docs", "score": 0.75},
        ]
        results = DevRagClient._parse_search_results(raw)
        assert len(results) == 2
        assert all(isinstance(r, SearchResult) for r in results)
        assert results[0].file_path == "docs/api.md"
        assert results[0].score == 0.92
        assert results[0].rank == 1
        assert results[0].excerpt == "API documentation..."
        assert results[0].corpus == CorpusType.GOVERNANCE
        assert results[1].rank == 2

    def test_parse_search_results_empty(self):
        results = DevRagClient._parse_search_results([])
        assert results == []
