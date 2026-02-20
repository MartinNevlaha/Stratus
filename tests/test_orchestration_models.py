"""Tests for orchestration/models.py — enums and Pydantic models."""

from __future__ import annotations

import json
from datetime import datetime

from stratus.orchestration.models import (
    FindingSeverity,
    OrchestratorMode,
    PlanStatus,
    ReviewFinding,
    ReviewVerdict,
    SpecPhase,
    SpecState,
    TeamConfig,
    TeammateInfo,
    TeammateStatus,
    TeamState,
    Verdict,
    WorktreeInfo,
)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestSpecPhase:
    def test_values(self):
        assert SpecPhase.PLAN == "plan"
        assert SpecPhase.IMPLEMENT == "implement"
        assert SpecPhase.VERIFY == "verify"
        assert SpecPhase.LEARN == "learn"

    def test_is_str(self):
        assert isinstance(SpecPhase.PLAN, str)


class TestPlanStatus:
    def test_values(self):
        assert PlanStatus.PENDING == "pending"
        assert PlanStatus.APPROVED == "approved"
        assert PlanStatus.IMPLEMENTING == "implementing"
        assert PlanStatus.VERIFYING == "verifying"
        assert PlanStatus.COMPLETE == "complete"
        assert PlanStatus.FAILED == "failed"

    def test_is_str(self):
        assert isinstance(PlanStatus.PENDING, str)


class TestVerdict:
    def test_values(self):
        assert Verdict.PASS == "pass"
        assert Verdict.FAIL == "fail"

    def test_is_str(self):
        assert isinstance(Verdict.PASS, str)


class TestFindingSeverity:
    def test_values(self):
        assert FindingSeverity.MUST_FIX == "must_fix"
        assert FindingSeverity.SHOULD_FIX == "should_fix"
        assert FindingSeverity.SUGGESTION == "suggestion"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TestReviewFinding:
    def test_basic_creation(self):
        f = ReviewFinding(
            file_path="src/main.py",
            line=42,
            severity=FindingSeverity.MUST_FIX,
            description="Missing error handling",
        )
        assert f.file_path == "src/main.py"
        assert f.line == 42
        assert f.severity == FindingSeverity.MUST_FIX
        assert f.description == "Missing error handling"

    def test_optional_line(self):
        f = ReviewFinding(
            file_path="src/main.py",
            severity=FindingSeverity.SUGGESTION,
            description="Consider renaming",
        )
        assert f.line is None

    def test_serialization_roundtrip(self):
        f = ReviewFinding(
            file_path="src/main.py",
            line=10,
            severity=FindingSeverity.SHOULD_FIX,
            description="Unused import",
        )
        data = json.loads(f.model_dump_json())
        f2 = ReviewFinding(**data)
        assert f2 == f


class TestReviewVerdict:
    def test_basic_creation(self):
        v = ReviewVerdict(
            reviewer="compliance",
            verdict=Verdict.PASS,
            findings=[],
            raw_output="Verdict: PASS",
        )
        assert v.reviewer == "compliance"
        assert v.verdict == Verdict.PASS
        assert v.findings == []

    def test_with_findings(self):
        finding = ReviewFinding(
            file_path="src/app.py",
            line=5,
            severity=FindingSeverity.MUST_FIX,
            description="SQL injection",
        )
        v = ReviewVerdict(
            reviewer="quality",
            verdict=Verdict.FAIL,
            findings=[finding],
            raw_output="Verdict: FAIL\n- must_fix: SQL injection",
        )
        assert len(v.findings) == 1
        assert v.findings[0].severity == FindingSeverity.MUST_FIX


class TestWorktreeInfo:
    def test_basic_creation(self):
        w = WorktreeInfo(
            path="/project/.worktrees/spec-my-feature-abc12345",
            branch="spec/my-feature",
            base_branch="main",
            slug="my-feature",
        )
        assert w.path == "/project/.worktrees/spec-my-feature-abc12345"
        assert w.branch == "spec/my-feature"
        assert w.base_branch == "main"
        assert w.slug == "my-feature"

    def test_serialization_roundtrip(self):
        w = WorktreeInfo(
            path="/tmp/wt",
            branch="spec/test",
            base_branch="main",
            slug="test",
        )
        data = json.loads(w.model_dump_json())
        w2 = WorktreeInfo(**data)
        assert w2 == w


class TestSpecState:
    def test_minimal_creation(self):
        s = SpecState(
            phase=SpecPhase.PLAN,
            slug="my-feature",
        )
        assert s.phase == SpecPhase.PLAN
        assert s.slug == "my-feature"
        assert s.plan_status == PlanStatus.PENDING
        assert s.plan_path is None
        assert s.worktree is None
        assert s.current_task == 0
        assert s.total_tasks == 0
        assert s.completed_tasks == 0
        assert s.review_iteration == 0
        assert s.max_review_iterations == 3

    def test_full_creation(self):
        wt = WorktreeInfo(
            path="/tmp/wt",
            branch="spec/feat",
            base_branch="main",
            slug="feat",
        )
        s = SpecState(
            phase=SpecPhase.IMPLEMENT,
            plan_path="/path/to/plan.md",
            plan_status=PlanStatus.IMPLEMENTING,
            slug="feat",
            worktree=wt,
            current_task=2,
            total_tasks=5,
            completed_tasks=1,
            review_iteration=1,
            max_review_iterations=5,
        )
        assert s.phase == SpecPhase.IMPLEMENT
        assert s.plan_path == "/path/to/plan.md"
        assert s.worktree is not None
        assert s.worktree.branch == "spec/feat"
        assert s.current_task == 2
        assert s.total_tasks == 5

    def test_last_updated_auto_set(self):
        s = SpecState(phase=SpecPhase.PLAN, slug="test")
        assert s.last_updated is not None
        # Should be a valid ISO timestamp
        dt = datetime.fromisoformat(s.last_updated)
        assert dt.tzinfo is not None

    def test_serialization_roundtrip(self):
        s = SpecState(
            phase=SpecPhase.VERIFY,
            slug="my-slug",
            plan_path="/plan.md",
            plan_status=PlanStatus.VERIFYING,
            review_iteration=2,
        )
        data = json.loads(s.model_dump_json())
        s2 = SpecState(**data)
        assert s2.phase == s.phase
        assert s2.slug == s.slug
        assert s2.plan_path == s.plan_path
        assert s2.review_iteration == s.review_iteration


# ---------------------------------------------------------------------------
# New enums (Phase 4 completion)
# ---------------------------------------------------------------------------


class TestOrchestratorMode:
    def test_values(self):
        assert OrchestratorMode.TASK_TOOL == "task-tool"
        assert OrchestratorMode.AGENT_TEAMS == "agent-teams"

    def test_is_str(self):
        assert isinstance(OrchestratorMode.TASK_TOOL, str)


class TestTeammateStatus:
    def test_values(self):
        assert TeammateStatus.IDLE == "idle"
        assert TeammateStatus.WORKING == "working"
        assert TeammateStatus.SHUTTING_DOWN == "shutting_down"
        assert TeammateStatus.ERROR == "error"

    def test_is_str(self):
        assert isinstance(TeammateStatus.IDLE, str)


# ---------------------------------------------------------------------------
# New Pydantic models (Phase 4 completion)
# ---------------------------------------------------------------------------


class TestTeamConfig:
    def test_defaults(self):
        tc = TeamConfig()
        assert tc.name == ""
        assert tc.mode == OrchestratorMode.TASK_TOOL
        assert tc.teammate_mode == "auto"
        assert tc.delegate_mode is False
        assert tc.require_plan_approval is True
        assert tc.max_teammates == 5

    def test_custom_values(self):
        tc = TeamConfig(
            name="my-team",
            mode=OrchestratorMode.AGENT_TEAMS,
            teammate_mode="tmux",
            delegate_mode=True,
            require_plan_approval=False,
            max_teammates=3,
        )
        assert tc.name == "my-team"
        assert tc.mode == OrchestratorMode.AGENT_TEAMS
        assert tc.teammate_mode == "tmux"
        assert tc.delegate_mode is True
        assert tc.require_plan_approval is False
        assert tc.max_teammates == 3

    def test_serialization_roundtrip(self):
        tc = TeamConfig(name="test", mode=OrchestratorMode.AGENT_TEAMS)
        data = json.loads(tc.model_dump_json())
        tc2 = TeamConfig(**data)
        assert tc2 == tc


class TestTeammateInfo:
    def test_creation(self):
        ti = TeammateInfo(
            name="reviewer-1",
            agent_type="delivery-spec-reviewer-compliance",
        )
        assert ti.name == "reviewer-1"
        assert ti.agent_type == "delivery-spec-reviewer-compliance"
        assert ti.agent_id is None
        assert ti.status == TeammateStatus.IDLE
        assert ti.current_task is None

    def test_with_active_task(self):
        ti = TeammateInfo(
            name="impl-1",
            agent_type="backend-implementer",
            agent_id="abc123",
            status=TeammateStatus.WORKING,
            current_task="task-42",
        )
        assert ti.agent_id == "abc123"
        assert ti.status == TeammateStatus.WORKING
        assert ti.current_task == "task-42"

    def test_serialization_roundtrip(self):
        ti = TeammateInfo(
            name="test",
            agent_type="qa",
            status=TeammateStatus.ERROR,
        )
        data = json.loads(ti.model_dump_json())
        ti2 = TeammateInfo(**data)
        assert ti2 == ti


class TestTeamState:
    def test_creation(self):
        config = TeamConfig(name="review-team")
        ts = TeamState(config=config)
        assert ts.config.name == "review-team"
        assert ts.teammates == []
        assert ts.lead_session_id is None
        assert ts.created_at is not None

    def test_with_teammates(self):
        config = TeamConfig(name="impl-team", max_teammates=3)
        t1 = TeammateInfo(name="impl-1", agent_type="backend")
        t2 = TeammateInfo(name="impl-2", agent_type="frontend")
        ts = TeamState(
            config=config,
            teammates=[t1, t2],
            lead_session_id="session-xyz",
        )
        assert len(ts.teammates) == 2
        assert ts.lead_session_id == "session-xyz"

    def test_serialization_roundtrip(self):
        config = TeamConfig(name="test-team")
        t = TeammateInfo(name="t1", agent_type="qa")
        ts = TeamState(config=config, teammates=[t])
        data = json.loads(ts.model_dump_json())
        ts2 = TeamState(**data)
        assert ts2.config == ts.config
        assert len(ts2.teammates) == 1
        assert ts2.teammates[0].name == "t1"
