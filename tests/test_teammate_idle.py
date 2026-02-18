"""Tests for hooks/teammate_idle.py — TeammateIdle quality gate hook."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from stratus.hooks.teammate_idle import evaluate_idle, main


class TestEvaluateIdle:
    def test_valid_verdict_pass(self):
        payload = {
            "teammate_name": "reviewer-1",
            "output": "Verdict: PASS\nNo issues found.",
        }
        exit_code, _msg = evaluate_idle(payload)
        assert exit_code == 0

    def test_valid_verdict_fail(self):
        payload = {
            "teammate_name": "reviewer-1",
            "output": "Verdict: FAIL\n- must_fix: src/main.py — Missing check",
        }
        exit_code, _msg = evaluate_idle(payload)
        assert exit_code == 0

    def test_missing_verdict_returns_exit2(self):
        payload = {
            "teammate_name": "reviewer-1",
            "output": "I looked at the code and it seems fine.",
        }
        exit_code, msg = evaluate_idle(payload)
        assert exit_code == 2
        assert "verdict" in msg.lower()

    def test_empty_output_returns_exit2(self):
        payload = {
            "teammate_name": "reviewer-1",
            "output": "",
        }
        exit_code, _msg = evaluate_idle(payload)
        assert exit_code == 2

    def test_missing_output_key_returns_exit0(self):
        payload = {"teammate_name": "reviewer-1"}
        exit_code, _msg = evaluate_idle(payload)
        assert exit_code == 0

    def test_empty_payload_returns_exit0(self):
        exit_code, _msg = evaluate_idle({})
        assert exit_code == 0

    def test_non_review_teammate_skipped(self):
        payload = {
            "teammate_name": "impl-1",
            "task_type": "implementation",
            "output": "Done implementing.",
        }
        exit_code, _msg = evaluate_idle(payload)
        assert exit_code == 0

    def test_exception_returns_exit0(self):
        """Hook must never crash — internal errors → exit 0."""
        exit_code, _msg = evaluate_idle(None)  # pyright: ignore[reportArgumentType]
        assert exit_code == 0

    def test_verdict_case_insensitive(self):
        payload = {
            "teammate_name": "reviewer-1",
            "output": "verdict: pass",
        }
        exit_code, _msg = evaluate_idle(payload)
        assert exit_code == 0

    def test_verdict_with_extra_whitespace(self):
        payload = {
            "teammate_name": "reviewer-1",
            "output": "Verdict :  PASS",
        }
        exit_code, _msg = evaluate_idle(payload)
        assert exit_code == 0


class TestMain:
    def test_main_allows_valid_verdict(self):
        payload = {
            "teammate_name": "reviewer-1",
            "output": "Verdict: PASS\nAll good.",
        }
        with patch("stratus.hooks._common.read_hook_input", return_value=payload):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_rejects_missing_verdict(self, capsys: pytest.CaptureFixture[str]):
        payload = {
            "teammate_name": "reviewer-1",
            "output": "I reviewed and everything seems fine.",
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
