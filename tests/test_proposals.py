"""Tests for learning/proposals.py — proposal generation + LLM prompt templates."""

from __future__ import annotations

import pytest

from stratus.learning.config import LearningConfig
from stratus.learning.database import LearningDatabase
from stratus.learning.models import (
    DetectionType,
    PatternCandidate,
    ProposalType,
    Sensitivity,
)
from stratus.learning.proposals import (
    ProposalGenerator,
    _check_existing_rules,
    _map_detection_to_proposal_type,
    build_llm_prompt,
)


@pytest.fixture
def db():
    database = LearningDatabase(":memory:")
    yield database
    database.close()


@pytest.fixture
def config():
    return LearningConfig(global_enabled=True, sensitivity=Sensitivity.MODERATE)


def _make_candidate(**overrides) -> PatternCandidate:
    defaults = dict(
        id="cand-1",
        detection_type=DetectionType.CODE_PATTERN,
        count=5,
        confidence_raw=0.7,
        confidence_final=0.65,
        files=["src/auth.py", "src/billing.py", "src/users.py"],
        description="Repeated error handling pattern",
        instances=[
            {"file": "src/auth.py", "line": 42},
            {"file": "src/billing.py", "line": 15},
        ],
    )
    defaults.update(overrides)
    return PatternCandidate(**defaults)


class TestBuildLlmPrompt:
    def test_contains_detection_type(self):
        c = _make_candidate()
        prompt = build_llm_prompt(c)
        assert "code_pattern" in prompt

    def test_contains_count(self):
        c = _make_candidate(count=7)
        prompt = build_llm_prompt(c)
        assert "7" in prompt

    def test_contains_files(self):
        c = _make_candidate()
        prompt = build_llm_prompt(c)
        assert "src/auth.py" in prompt

    def test_contains_questions(self):
        c = _make_candidate()
        prompt = build_llm_prompt(c)
        assert "genuine" in prompt.lower() or "pattern" in prompt.lower()

    def test_contains_description(self):
        c = _make_candidate(description="Custom description here")
        prompt = build_llm_prompt(c)
        assert "Custom description here" in prompt


class TestMapDetectionToProposalType:
    def test_code_pattern_maps_to_rule(self):
        assert _map_detection_to_proposal_type(DetectionType.CODE_PATTERN) == ProposalType.RULE

    def test_structural_change_maps_to_template(self):
        result = _map_detection_to_proposal_type(DetectionType.STRUCTURAL_CHANGE)
        assert result == ProposalType.TEMPLATE

    def test_fix_pattern_maps_to_rule(self):
        assert _map_detection_to_proposal_type(DetectionType.FIX_PATTERN) == ProposalType.RULE

    def test_import_pattern_maps_to_rule(self):
        assert _map_detection_to_proposal_type(DetectionType.IMPORT_PATTERN) == ProposalType.RULE

    def test_service_detected_maps_to_project_graph(self):
        result = _map_detection_to_proposal_type(DetectionType.SERVICE_DETECTED)
        assert result == ProposalType.PROJECT_GRAPH

    def test_config_pattern_maps_to_rule(self):
        assert _map_detection_to_proposal_type(DetectionType.CONFIG_PATTERN) == ProposalType.RULE


class TestCheckExistingRules:
    def test_no_match_when_no_rules_dir(self, tmp_path):
        c = _make_candidate()
        assert _check_existing_rules(c, tmp_path / "nonexistent") is False

    def test_no_match_with_empty_rules(self, tmp_path):
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        c = _make_candidate()
        assert _check_existing_rules(c, rules_dir) is False

    def test_match_when_similar_rule_exists(self, tmp_path):
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "error-handling.md").write_text(
            "# Error Handling\nAlways use consistent error handling pattern"
        )
        c = _make_candidate(description="Repeated error handling pattern")
        assert _check_existing_rules(c, rules_dir) is True


class TestProposalGenerator:
    def test_generates_proposals(self, config, db: LearningDatabase):
        gen = ProposalGenerator(config, db)
        candidates = [_make_candidate()]
        proposals = gen.generate_proposals(candidates)
        assert len(proposals) >= 1
        assert proposals[0].candidate_id == "cand-1"
        assert proposals[0].type == ProposalType.RULE

    def test_empty_candidates(self, config, db: LearningDatabase):
        gen = ProposalGenerator(config, db)
        assert gen.generate_proposals([]) == []

    def test_deduplication(self, config, db: LearningDatabase):
        gen = ProposalGenerator(config, db)
        candidates = [
            _make_candidate(id="c1", description="Same pattern"),
            _make_candidate(id="c2", description="Same pattern"),
        ]
        proposals = gen.generate_proposals(candidates)
        # Should deduplicate identical descriptions
        assert len(proposals) == 1

    def test_proposal_includes_content(self, config, db: LearningDatabase):
        gen = ProposalGenerator(config, db)
        proposals = gen.generate_proposals([_make_candidate()])
        assert proposals[0].proposed_content != ""

    def test_respects_max_proposals(self, db: LearningDatabase):
        config = LearningConfig(
            global_enabled=True,
            sensitivity=Sensitivity.AGGRESSIVE,
            max_proposals_per_session=2,
        )
        gen = ProposalGenerator(config, db)
        candidates = [
            _make_candidate(id=f"c{i}", description=f"Pattern {i}")
            for i in range(5)
        ]
        proposals = gen.generate_proposals(candidates)
        assert len(proposals) <= 2

    def test_skips_candidate_with_existing_rule(self, config, db, tmp_path):
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "error-handling.md").write_text(
            "# Error Handling\nAlways use consistent error handling pattern"
        )
        gen = ProposalGenerator(config, db)
        candidates = [_make_candidate(description="Repeated error handling pattern")]
        proposals = gen.generate_proposals(candidates, rules_dir=rules_dir)
        assert len(proposals) == 0

    def test_passes_candidate_without_existing_rule(self, config, db, tmp_path):
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "naming.md").write_text("# Naming\nUse snake_case for variables")
        gen = ProposalGenerator(config, db)
        candidates = [_make_candidate(description="Repeated error handling pattern")]
        proposals = gen.generate_proposals(candidates, rules_dir=rules_dir)
        assert len(proposals) == 1

    def test_proposed_path_set_for_rule(self, config, db, tmp_path):
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        gen = ProposalGenerator(config, db)
        candidates = [_make_candidate()]
        proposals = gen.generate_proposals(
            candidates, rules_dir=rules_dir, project_root=tmp_path,
        )
        assert len(proposals) == 1
        assert proposals[0].proposed_path is not None
        assert ".claude/rules" in proposals[0].proposed_path

    def test_proposed_path_set_for_template(self, config, db, tmp_path):
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        gen = ProposalGenerator(config, db)
        candidates = [_make_candidate(
            detection_type=DetectionType.STRUCTURAL_CHANGE,
            description="Module structure pattern",
        )]
        proposals = gen.generate_proposals(
            candidates, rules_dir=rules_dir, project_root=tmp_path,
        )
        assert len(proposals) == 1
        assert proposals[0].proposed_path is not None
        assert ".claude/templates" in proposals[0].proposed_path

    def test_rules_dir_none_skips_check(self, config, db):
        gen = ProposalGenerator(config, db)
        candidates = [_make_candidate()]
        proposals = gen.generate_proposals(candidates, rules_dir=None)
        assert len(proposals) == 1
