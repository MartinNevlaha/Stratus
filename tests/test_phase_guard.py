"""Tests for the phase guard hook."""

from __future__ import annotations

from stratus.hooks.phase_guard import evaluate_phase_consistency


class TestEvaluatePhaseConsistency:
    def test_no_agent_returns_empty(self):
        assert evaluate_phase_consistency(None, "verify") == ""

    def test_no_phase_returns_empty(self):
        assert evaluate_phase_consistency("delivery-implementation-expert", None) == ""

    def test_implement_agent_in_verify_warns(self):
        msg = evaluate_phase_consistency("delivery-implementation-expert", "verify")
        assert "phase inconsistency" in msg.lower()
        assert "implementation agent" in msg.lower()

    def test_review_agent_in_implement_warns(self):
        msg = evaluate_phase_consistency("delivery-spec-reviewer-compliance", "implement")
        assert "phase inconsistency" in msg.lower()
        assert "review agent" in msg.lower()

    def test_review_agent_in_implementation_warns(self):
        msg = evaluate_phase_consistency("delivery-qa-engineer", "implementation")
        assert "phase inconsistency" in msg.lower()

    def test_correct_agent_in_implement(self):
        msg = evaluate_phase_consistency("delivery-implementation-expert", "implement")
        assert msg == ""

    def test_correct_agent_in_verify(self):
        msg = evaluate_phase_consistency("delivery-spec-reviewer-compliance", "verify")
        assert msg == ""

    def test_unknown_agent_no_warning(self):
        msg = evaluate_phase_consistency("custom-agent", "verify")
        assert msg == ""

    def test_delivery_backend_in_verify_warns(self):
        msg = evaluate_phase_consistency("delivery-backend-engineer", "verify")
        assert "phase inconsistency" in msg.lower()

    def test_delivery_qa_in_implement_warns(self):
        msg = evaluate_phase_consistency("delivery-qa-engineer", "implementation")
        assert "phase inconsistency" in msg.lower()

    def test_plan_phase_no_warnings(self):
        msg = evaluate_phase_consistency("delivery-implementation-expert", "plan")
        assert msg == ""
