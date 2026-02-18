"""Tests for retrieval/index_state.py — TDD RED phase first."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from stratus.retrieval.models import IndexStatus


def test_read_index_state_missing_file(tmp_path: Path) -> None:
    """Returns default IndexStatus when index-state.json does not exist."""
    from stratus.retrieval.index_state import read_index_state

    result = read_index_state(tmp_path)

    assert isinstance(result, IndexStatus)
    assert result.last_indexed_commit is None
    assert result.last_indexed_at is None
    assert result.total_files == 0
    assert result.stale is True

def test_write_and_read_roundtrip(tmp_path: Path) -> None:
    """write_index_state then read_index_state returns same values."""
    from stratus.retrieval.index_state import read_index_state, write_index_state

    status = IndexStatus(
        last_indexed_commit="abc123",
        last_indexed_at="2026-01-01T00:00:00Z",
        total_files=42,
        model="nomic-embed-text-v1.5",
        stale=False,
    )

    write_index_state(tmp_path, status)
    result = read_index_state(tmp_path)

    assert result.last_indexed_commit == "abc123"
    assert result.last_indexed_at == "2026-01-01T00:00:00Z"
    assert result.total_files == 42
    assert result.model == "nomic-embed-text-v1.5"
    assert result.stale is False

def test_get_current_commit_success(tmp_path: Path) -> None:
    """Returns commit hash string when git succeeds."""
    from stratus.retrieval.index_state import get_current_commit

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "deadbeefcafe1234\n"

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = get_current_commit(tmp_path)

    assert result == "deadbeefcafe1234"
    mock_run.assert_called_once_with(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=tmp_path,
    )

def test_get_current_commit_failure(tmp_path: Path) -> None:
    """Returns None when git command fails."""
    from stratus.retrieval.index_state import get_current_commit

    mock_result = MagicMock()
    mock_result.returncode = 128

    with patch("subprocess.run", return_value=mock_result):
        result = get_current_commit(tmp_path)

    assert result is None

def test_get_current_commit_exception(tmp_path: Path) -> None:
    """Returns None when subprocess raises an exception."""
    from stratus.retrieval.index_state import get_current_commit

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 10)):
        result = get_current_commit(tmp_path)

    assert result is None

def test_check_staleness_when_different_commits(tmp_path: Path) -> None:
    """Returns True when HEAD differs from last indexed commit."""
    from stratus.retrieval.index_state import check_staleness, write_index_state

    write_index_state(
        tmp_path,
        IndexStatus(last_indexed_commit="oldcommit", stale=False),
    )

    with patch(
        "stratus.retrieval.index_state.get_current_commit",
        return_value="newcommit",
    ):
        result = check_staleness(tmp_path, tmp_path)

    assert result is True

def test_check_staleness_when_same_commit(tmp_path: Path) -> None:
    """Returns False when HEAD matches last indexed commit."""
    from stratus.retrieval.index_state import check_staleness, write_index_state

    write_index_state(
        tmp_path,
        IndexStatus(last_indexed_commit="abc123", stale=False),
    )

    with patch(
        "stratus.retrieval.index_state.get_current_commit",
        return_value="abc123",
    ):
        result = check_staleness(tmp_path, tmp_path)

    assert result is False

def test_check_staleness_when_no_index(tmp_path: Path) -> None:
    """Returns True when index-state.json does not exist."""
    from stratus.retrieval.index_state import check_staleness

    with patch(
        "stratus.retrieval.index_state.get_current_commit",
        return_value="abc123",
    ):
        result = check_staleness(tmp_path, tmp_path)

    assert result is True

def test_get_changed_files_success(tmp_path: Path) -> None:
    """Returns list of changed file paths when git diff succeeds."""
    from stratus.retrieval.index_state import get_changed_files

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "src/foo.py\nsrc/bar.py\n"

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = get_changed_files(tmp_path, "abc123")

    assert result == ["src/foo.py", "src/bar.py"]
    mock_run.assert_called_once_with(
        ["git", "diff", "--name-only", "abc123..HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=tmp_path,
    )

def test_get_changed_files_failure(tmp_path: Path) -> None:
    """Returns empty list when git diff fails."""
    from stratus.retrieval.index_state import get_changed_files

    mock_result = MagicMock()
    mock_result.returncode = 128

    with patch("subprocess.run", return_value=mock_result):
        result = get_changed_files(tmp_path, "abc123")

    assert result == []

def test_read_index_state_corrupted_json(tmp_path: Path) -> None:
    """Returns default IndexStatus when JSON is corrupted."""
    from stratus.retrieval.index_state import read_index_state

    state_file = tmp_path / "index-state.json"
    state_file.write_text("{ not valid json }")

    result = read_index_state(tmp_path)

    assert isinstance(result, IndexStatus)
    assert result.last_indexed_commit is None
    assert result.stale is True
