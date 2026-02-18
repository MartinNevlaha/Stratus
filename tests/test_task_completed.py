"""Tests for hooks/task_completed.py — TaskCompleted quality gate hook."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from stratus.hooks.task_completed import evaluate_completion, main


class TestEvaluateCompletion:
    def test_valid_output(self):
        payload = {
            "task_id": "task-1",
            "output": "All tests pass. 5 passed in 0.3s",
        }
        exit_code, _msg = evaluate_completion(payload)
        assert exit_code == 0

    def test_empty_output_passes(self):
        payload = {
            "task_id": "task-1",
            "output": "",
        }
        exit_code, _msg = evaluate_completion(payload)
        assert exit_code == 0

    def test_whitespace_only_output_passes(self):
        payload = {
            "task_id": "task-1",
            "output": "   \n  ",
        }
        exit_code, _msg = evaluate_completion(payload)
        assert exit_code == 0

    def test_review_task_with_verdict(self):
        payload = {
            "task_id": "review-1",
            "task_type": "review",
            "output": "Verdict: PASS\nAll looks good.",
        }
        exit_code, _msg = evaluate_completion(payload)
        assert exit_code == 0

    def test_review_task_missing_verdict(self):
        payload = {
            "task_id": "review-1",
            "task_type": "review",
            "output": "I reviewed the code and it looks fine.",
        }
        exit_code, msg = evaluate_completion(payload)
        assert exit_code == 2
        assert "verdict" in msg.lower()

    def test_code_task_with_test_failure(self):
        payload = {
            "task_id": "impl-1",
            "task_type": "implementation",
            "output": "FAILED tests/test_foo.py::test_bar - AssertionError\n1 failed",
        }
        exit_code, msg = evaluate_completion(payload)
        assert exit_code == 2
        assert "fail" in msg.lower()

    def test_code_task_with_tests_passing(self):
        payload = {
            "task_id": "impl-1",
            "task_type": "implementation",
            "output": "All tests pass.\n10 passed in 1.2s",
        }
        exit_code, _msg = evaluate_completion(payload)
        assert exit_code == 0

    def test_missing_task_id(self):
        payload = {"output": "some output"}
        exit_code, _msg = evaluate_completion(payload)
        assert exit_code == 0

    def test_empty_payload(self):
        exit_code, _msg = evaluate_completion({})
        assert exit_code == 0

    def test_exception_returns_exit0(self):
        """Hook must never crash — internal errors → exit 0."""
        exit_code, _msg = evaluate_completion(None)  # pyright: ignore[reportArgumentType]
        assert exit_code == 0

    def test_general_task_nonempty_passes(self):
        payload = {
            "task_id": "gen-1",
            "output": "Completed the documentation update.",
        }
        exit_code, _msg = evaluate_completion(payload)
        assert exit_code == 0

    def test_failed_keyword_in_nontest_context_passes(self):
        """The word 'failed' in prose shouldn't trigger rejection for general tasks."""
        payload = {
            "task_id": "gen-1",
            "output": "Previously failed attempts were resolved.",
        }
        exit_code, _msg = evaluate_completion(payload)
        assert exit_code == 0


class TestMain:
    def test_main_allows_valid_output(self):
        payload = {
            "task_id": "task-1",
            "task_type": "review",
            "output": "Verdict: PASS\nAll tests pass.",
        }
        with patch("stratus.hooks._common.read_hook_input", return_value=payload):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_rejects_review_without_verdict(self, capsys: pytest.CaptureFixture[str]):
        payload = {
            "task_id": "review-1",
            "task_type": "review",
            "output": "I reviewed the code and everything looks fine.",
        }
        with patch("stratus.hooks._common.read_hook_input", return_value=payload):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "verdict" in captured.err.lower()

    def test_main_handles_empty_input(self):
        with patch("stratus.hooks._common.read_hook_input", return_value={}):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
