"""Tests for retrieval/vexor.py — VexorClient and parse_porcelain."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from stratus.retrieval.config import VexorConfig
from stratus.retrieval.models import CorpusType, RetrievalResponse
from stratus.retrieval.vexor import VexorClient

_PATCH = "stratus.retrieval.vexor.subprocess.run"


# ---------------------------------------------------------------------------
# TestVexorClient
# ---------------------------------------------------------------------------


class TestVexorClient:
    def _make_client(self, binary_path: str = "vexor") -> VexorClient:
        return VexorClient(VexorConfig(binary_path=binary_path))

    # -- is_available --------------------------------------------------------

    def test_is_available_when_binary_exists(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch(_PATCH, return_value=mock_result) as mock_run:
            client = self._make_client()
            assert client.is_available() is True
            mock_run.assert_called_once_with(
                ["vexor", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )

    def test_is_available_when_binary_missing(self):
        with patch(_PATCH, side_effect=FileNotFoundError):
            client = self._make_client()
            assert client.is_available() is False

    # -- search --------------------------------------------------------------

    def test_search_builds_correct_command(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        with patch(_PATCH, return_value=mock_result) as mock_run:
            client = self._make_client()
            client.search("my query", top=5, mode="semantic")
            args, _ = mock_run.call_args
            cmd = args[0]
            assert cmd[0] == "vexor"
            assert "search" in cmd
            assert "--format" in cmd
            assert "porcelain" in cmd
            assert "--porcelain" not in cmd
            assert "--top" in cmd
            assert "5" in cmd
            assert "--mode" in cmd
            assert "semantic" in cmd
            assert "my query" in cmd

    def test_search_default_mode_is_auto(self):
        """Default mode must be 'auto', not 'hybrid' (hybrid is no longer valid)."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        with patch(_PATCH, return_value=mock_result) as mock_run:
            client = self._make_client()
            client.search("query")
            args, _ = mock_run.call_args
            cmd = args[0]
            mode_idx = cmd.index("--mode")
            assert cmd[mode_idx + 1] == "auto"

    def test_search_command_uses_format_porcelain_as_separate_args(self):
        """--format and porcelain must be separate args, not --porcelain."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        with patch(_PATCH, return_value=mock_result) as mock_run:
            client = self._make_client()
            client.search("query")
            args, _ = mock_run.call_args
            cmd = args[0]
            assert "--porcelain" not in cmd
            fmt_idx = cmd.index("--format")
            assert cmd[fmt_idx + 1] == "porcelain"

    def test_search_with_path_and_ext(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        with patch(_PATCH, return_value=mock_result) as mock_run:
            client = self._make_client()
            client.search("query", path="/project/src", ext="py")
            args, _ = mock_run.call_args
            cmd = args[0]
            assert "--path" in cmd
            assert "/project/src" in cmd
            assert "--ext" in cmd
            assert "py" in cmd

    def test_search_returns_retrieval_response(self):
        porcelain = "1\t0.95\tsrc/main.py\t0\t10\t20\tdef main :: def main(): ..."
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = porcelain
        with patch(_PATCH, return_value=mock_result):
            client = self._make_client()
            response = client.search("main")
            assert isinstance(response, RetrievalResponse)
            assert response.corpus == CorpusType.CODE
            assert len(response.results) == 1
            assert response.results[0].file_path == "src/main.py"
            assert response.results[0].score == 0.95
            assert response.query_time_ms >= 0

    def test_search_handles_timeout(self):
        with patch(_PATCH, side_effect=subprocess.TimeoutExpired(cmd="vexor", timeout=10)):
            client = self._make_client()
            response = client.search("query")
            assert isinstance(response, RetrievalResponse)
            assert response.results == []
            assert response.corpus == CorpusType.CODE

    def test_search_handles_missing_binary(self):
        with patch(_PATCH, side_effect=FileNotFoundError):
            client = self._make_client()
            response = client.search("query")
            assert isinstance(response, RetrievalResponse)
            assert response.results == []

    def test_search_handles_nonzero_exit(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error: no index found"
        with patch(_PATCH, return_value=mock_result):
            client = self._make_client()
            response = client.search("query")
            assert isinstance(response, RetrievalResponse)
            assert response.results == []

    # -- index ---------------------------------------------------------------

    def test_index_success(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Indexed 42 files."
        with patch(_PATCH, return_value=mock_result) as mock_run:
            client = self._make_client()
            result = client.index()
            assert result["status"] == "ok"
            assert "output" in result
            args, _ = mock_run.call_args
            cmd = args[0]
            assert cmd[0] == "vexor"
            assert "index" in cmd

    def test_index_with_clear_flag(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        with patch(_PATCH, return_value=mock_result) as mock_run:
            client = self._make_client()
            client.index(clear=True)
            args, _ = mock_run.call_args
            cmd = args[0]
            assert "--clear" in cmd

    def test_index_handles_error(self):
        with patch(_PATCH, side_effect=FileNotFoundError):
            client = self._make_client()
            result = client.index()
            assert result["status"] == "error"
            assert "message" in result


# ---------------------------------------------------------------------------
# TestParsePorcelain
# ---------------------------------------------------------------------------


class TestParsePorcelain:
    def test_parse_porcelain_single_result(self):
        output = "1\t0.95\tsrc/main.py\t0\t10\t20\tdef main :: def main(): ..."
        results = VexorClient.parse_porcelain(output)
        assert len(results) == 1
        r = results[0]
        assert r.rank == 1
        assert r.score == pytest.approx(0.95)
        assert r.file_path == "src/main.py"
        assert r.chunk_index == 0
        assert r.line_start == 10
        assert r.line_end == 20
        assert "def main(): ..." in r.excerpt
        assert r.corpus == CorpusType.CODE

    def test_parse_porcelain_multiple_results(self):
        output = (
            "1\t0.95\tsrc/main.py\t0\t10\t20\tdef main :: def main(): ...\n"
            "2\t0.82\tsrc/utils.py\t1\t30\t40\tHelper :: helper function"
        )
        results = VexorClient.parse_porcelain(output)
        assert len(results) == 2
        assert results[0].rank == 1
        assert results[1].rank == 2
        assert results[1].file_path == "src/utils.py"
        assert results[1].score == pytest.approx(0.82)
        assert results[1].chunk_index == 1

    def test_parse_porcelain_empty_output(self):
        results = VexorClient.parse_porcelain("")
        assert results == []

    def test_parse_porcelain_skips_blank_lines(self):
        output = (
            "1\t0.95\tsrc/main.py\t0\t10\t20\tdef main :: def main(): ...\n"
            "\n"
            "2\t0.82\tsrc/utils.py\t1\t30\t40\tHelper :: helper function\n"
            "\n"
        )
        results = VexorClient.parse_porcelain(output)
        assert len(results) == 2
