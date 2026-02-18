"""Tests for learning/models.py — enums and Pydantic models."""

from __future__ import annotations

from stratus.learning.models import (
    AnalysisResult,
    CandidateStatus,
    Decision,
    Detection,
    DetectionType,
    LLMAssessment,
    PatternCandidate,
    Proposal,
    ProposalStatus,
    ProposalType,
    Sensitivity,
)


class TestEnums:
    def test_detection_type_values(self):
        assert DetectionType.CODE_PATTERN == "code_pattern"
        assert DetectionType.STRUCTURAL_CHANGE == "structural_change"
        assert DetectionType.FIX_PATTERN == "fix_pattern"
        assert DetectionType.IMPORT_PATTERN == "import_pattern"
        assert DetectionType.CONFIG_PATTERN == "config_pattern"
        assert DetectionType.SERVICE_DETECTED == "service_detected"

    def test_candidate_status_values(self):
        assert CandidateStatus.PENDING == "pending"
        assert CandidateStatus.INTERPRETED == "interpreted"
        assert CandidateStatus.PROPOSED == "proposed"
        assert CandidateStatus.DECIDED == "decided"

    def test_proposal_type_values(self):
        assert ProposalType.RULE == "rule"
        assert ProposalType.SKILL == "skill"
        assert ProposalType.ADR == "adr"
        assert ProposalType.PROJECT_GRAPH == "project_graph"
        assert ProposalType.TEMPLATE == "template"

    def test_proposal_status_values(self):
        assert ProposalStatus.PENDING == "pending"
        assert ProposalStatus.PRESENTED == "presented"
        assert ProposalStatus.ACCEPTED == "accepted"
        assert ProposalStatus.REJECTED == "rejected"
        assert ProposalStatus.IGNORED == "ignored"
        assert ProposalStatus.SNOOZED == "snoozed"

    def test_decision_values(self):
        assert Decision.ACCEPT == "accept"
        assert Decision.REJECT == "reject"
        assert Decision.IGNORE == "ignore"
        assert Decision.SNOOZE == "snooze"

    def test_sensitivity_values(self):
        assert Sensitivity.CONSERVATIVE == "conservative"
        assert Sensitivity.MODERATE == "moderate"
        assert Sensitivity.AGGRESSIVE == "aggressive"


class TestDetection:
    def test_minimal_detection(self):
        d = Detection(
            type=DetectionType.CODE_PATTERN,
            count=3,
            confidence_raw=0.6,
            files=["a.py", "b.py"],
            description="Repeated error handler",
        )
        assert d.type == DetectionType.CODE_PATTERN
        assert d.count == 3
        assert d.confidence_raw == 0.6
        assert d.files == ["a.py", "b.py"]
        assert d.instances == []

    def test_detection_with_instances(self):
        d = Detection(
            type=DetectionType.FIX_PATTERN,
            count=5,
            confidence_raw=0.8,
            files=["x.py"],
            description="Same fix",
            instances=[{"commit": "abc", "msg": "fix auth"}],
        )
        assert len(d.instances) == 1
        assert d.instances[0]["commit"] == "abc"

    def test_detection_confidence_bounds(self):
        d = Detection(
            type=DetectionType.CODE_PATTERN,
            count=1,
            confidence_raw=0.0,
            files=[],
            description="test",
        )
        assert d.confidence_raw == 0.0

        d2 = Detection(
            type=DetectionType.CODE_PATTERN,
            count=1,
            confidence_raw=1.0,
            files=[],
            description="test",
        )
        assert d2.confidence_raw == 1.0


class TestPatternCandidate:
    def test_defaults(self):
        pc = PatternCandidate(
            id="cand-1",
            detection_type=DetectionType.IMPORT_PATTERN,
            count=4,
            confidence_raw=0.5,
            confidence_final=0.4,
            files=["a.py"],
            description="Repeated import",
        )
        assert pc.status == CandidateStatus.PENDING
        assert pc.instances == []
        assert pc.llm_assessment is None
        assert pc.description_hash is not None
        assert pc.detected_at is not None

    def test_all_fields(self):
        pc = PatternCandidate(
            id="cand-2",
            detection_type=DetectionType.STRUCTURAL_CHANGE,
            count=2,
            confidence_raw=0.7,
            confidence_final=0.65,
            files=["dir/a.py", "dir/b.py"],
            description="New service dirs",
            instances=[{"dir": "svc-a"}, {"dir": "svc-b"}],
            status=CandidateStatus.PROPOSED,
            description_hash="abc123",
        )
        assert pc.status == CandidateStatus.PROPOSED
        assert len(pc.instances) == 2

    def test_description_hash_auto_generated(self):
        pc1 = PatternCandidate(
            id="c1",
            detection_type=DetectionType.CODE_PATTERN,
            count=1,
            confidence_raw=0.5,
            confidence_final=0.5,
            files=[],
            description="Same error handler",
        )
        pc2 = PatternCandidate(
            id="c2",
            detection_type=DetectionType.CODE_PATTERN,
            count=1,
            confidence_raw=0.5,
            confidence_final=0.5,
            files=[],
            description="Same error handler",
        )
        # Same description -> same hash
        assert pc1.description_hash == pc2.description_hash

        pc3 = PatternCandidate(
            id="c3",
            detection_type=DetectionType.CODE_PATTERN,
            count=1,
            confidence_raw=0.5,
            confidence_final=0.5,
            files=[],
            description="Different description",
        )
        assert pc1.description_hash != pc3.description_hash


class TestProposal:
    def test_defaults(self):
        p = Proposal(
            id="prop-1",
            candidate_id="cand-1",
            type=ProposalType.RULE,
            title="Add error handler rule",
            description="Use consistent error handling",
            proposed_content="Always use try/except...",
            confidence=0.7,
        )
        assert p.status == ProposalStatus.PENDING
        assert p.proposed_path is None
        assert p.presented_at is None
        assert p.decided_at is None
        assert p.decision is None
        assert p.edited_content is None
        assert p.session_id is None

    def test_all_fields(self):
        p = Proposal(
            id="prop-2",
            candidate_id="cand-2",
            type=ProposalType.TEMPLATE,
            title="Service bootstrap template",
            description="Common service setup",
            proposed_content="template content",
            proposed_path=".claude/templates/service.md",
            confidence=0.85,
            status=ProposalStatus.ACCEPTED,
            decision=Decision.ACCEPT,
            session_id="sess-1",
        )
        assert p.proposed_path == ".claude/templates/service.md"
        assert p.decision == Decision.ACCEPT


class TestAnalysisResult:
    def test_defaults(self):
        r = AnalysisResult(
            detections=[],
            analyzed_commits=0,
            analysis_time_ms=100,
        )
        assert r.detections == []
        assert r.analyzed_commits == 0

    def test_with_detections(self):
        d = Detection(
            type=DetectionType.CODE_PATTERN,
            count=3,
            confidence_raw=0.6,
            files=["a.py"],
            description="test",
        )
        r = AnalysisResult(
            detections=[d],
            analyzed_commits=10,
            analysis_time_ms=500,
        )
        assert len(r.detections) == 1


class TestLLMAssessment:
    def test_fields(self):
        a = LLMAssessment(
            is_pattern=True,
            confidence=0.85,
            proposed_rule="Always handle errors consistently",
            reasoning="Found in 5 files across 3 directories",
        )
        assert a.is_pattern is True
        assert a.confidence == 0.85
        assert a.proposed_rule is not None

    def test_optional_fields(self):
        a = LLMAssessment(
            is_pattern=False,
            confidence=0.2,
        )
        assert a.proposed_rule is None
        assert a.reasoning is None
