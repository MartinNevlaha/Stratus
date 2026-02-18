"""Tests for learning/artifacts.py — artifact content generation and file writing."""

from __future__ import annotations

import json

from stratus.learning.models import Proposal, ProposalType


def _make_proposal(**overrides) -> Proposal:
    defaults = dict(
        id="prop-1",
        candidate_id="cand-1",
        type=ProposalType.RULE,
        title="Add rule: error handling",
        description="Consistent error handling across modules",
        proposed_content="Always wrap external calls in try/except",
        confidence=0.8,
    )
    defaults.update(overrides)
    return Proposal(**defaults)


class TestSlugFromTitle:
    def test_simple_title(self):
        from stratus.learning.artifacts import _slug_from_title

        result = _slug_from_title("Error Handling Pattern")
        assert result == "error-handling-pattern"

    def test_special_characters(self):
        from stratus.learning.artifacts import _slug_from_title

        result = _slug_from_title("Add rule: error/handling (v2)")
        # Should strip non-alphanumeric except hyphens
        assert "/" not in result
        assert "(" not in result
        assert ":" not in result

    def test_long_title_truncated(self):
        from stratus.learning.artifacts import _slug_from_title

        title = "A" * 100
        result = _slug_from_title(title)
        assert len(result) <= 60

    def test_collapses_multiple_hyphens(self):
        from stratus.learning.artifacts import _slug_from_title

        result = _slug_from_title("foo---bar   baz")
        assert "--" not in result


class TestComputeArtifactPath:
    def test_rule_path(self, tmp_path):
        from stratus.learning.artifacts import compute_artifact_path

        p = _make_proposal(type=ProposalType.RULE, title="Error handling")
        result = compute_artifact_path(p, tmp_path)
        assert result.parent == tmp_path / ".claude" / "rules"
        assert result.name.startswith("learning-")
        assert result.suffix == ".md"

    def test_adr_path(self, tmp_path):
        from stratus.learning.artifacts import compute_artifact_path

        p = _make_proposal(type=ProposalType.ADR, title="Use PostgreSQL")
        result = compute_artifact_path(p, tmp_path)
        assert result.parent == tmp_path / "docs" / "decisions"
        assert result.suffix == ".md"

    def test_template_path(self, tmp_path):
        from stratus.learning.artifacts import compute_artifact_path

        p = _make_proposal(type=ProposalType.TEMPLATE, title="Module template")
        result = compute_artifact_path(p, tmp_path)
        assert result.parent == tmp_path / ".claude" / "templates"
        assert result.suffix == ".md"

    def test_project_graph_path(self, tmp_path):
        from stratus.learning.artifacts import compute_artifact_path

        p = _make_proposal(type=ProposalType.PROJECT_GRAPH, title="Service graph")
        result = compute_artifact_path(p, tmp_path)
        assert result == tmp_path / ".ai-framework" / "project-graph.json"

    def test_skill_path(self, tmp_path):
        from stratus.learning.artifacts import compute_artifact_path

        p = _make_proposal(type=ProposalType.SKILL, title="Deploy skill")
        result = compute_artifact_path(p, tmp_path)
        assert ".claude" in str(result)
        assert "skills" in str(result)
        assert result.name == "prompt.md"


class TestGenerateArtifactContent:
    def test_rule_content_contains_title(self):
        from stratus.learning.artifacts import generate_artifact_content

        p = _make_proposal(type=ProposalType.RULE, title="Error handling rule")
        content = generate_artifact_content(p)
        assert "Error handling rule" in content

    def test_rule_content_contains_description(self):
        from stratus.learning.artifacts import generate_artifact_content

        p = _make_proposal(type=ProposalType.RULE, description="Handle errors consistently")
        content = generate_artifact_content(p)
        assert "Handle errors consistently" in content

    def test_adr_content_has_sections(self):
        from stratus.learning.artifacts import generate_artifact_content

        p = _make_proposal(type=ProposalType.ADR, title="Use PostgreSQL")
        content = generate_artifact_content(p)
        assert "Status" in content
        assert "Context" in content
        assert "Decision" in content
        assert "Consequences" in content

    def test_edited_content_used_verbatim(self):
        from stratus.learning.artifacts import generate_artifact_content

        p = _make_proposal(type=ProposalType.RULE)
        content = generate_artifact_content(p, edited_content="Custom rule text here")
        assert content == "Custom rule text here"

    def test_template_uses_proposed_content(self):
        from stratus.learning.artifacts import generate_artifact_content

        p = _make_proposal(type=ProposalType.TEMPLATE, proposed_content="Template body text")
        content = generate_artifact_content(p)
        assert "Template body text" in content

    def test_skill_content_contains_title(self):
        from stratus.learning.artifacts import generate_artifact_content

        p = _make_proposal(type=ProposalType.SKILL, title="Deploy automation")
        content = generate_artifact_content(p)
        assert "Deploy automation" in content


class TestCreateArtifact:
    def test_writes_file(self, tmp_path):
        from stratus.learning.artifacts import create_artifact

        p = _make_proposal(type=ProposalType.RULE, title="Error handling")
        result = create_artifact(p, tmp_path)
        assert result is not None
        assert result.exists()
        assert result.read_text() != ""

    def test_creates_parent_dirs(self, tmp_path):
        from stratus.learning.artifacts import create_artifact

        p = _make_proposal(type=ProposalType.ADR, title="Use PostgreSQL")
        result = create_artifact(p, tmp_path)
        assert result is not None
        assert result.parent.exists()

    def test_returns_none_on_error(self, tmp_path):
        from stratus.learning.artifacts import create_artifact

        p = _make_proposal(type=ProposalType.RULE, title="Test")
        # Make the target directory a file to cause an error
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.parent.mkdir(parents=True)
        rules_dir.write_text("not a directory")
        result = create_artifact(p, tmp_path)
        assert result is None

    def test_uses_edited_content(self, tmp_path):
        from stratus.learning.artifacts import create_artifact

        p = _make_proposal(type=ProposalType.RULE, title="Custom rule")
        result = create_artifact(p, tmp_path, edited_content="My custom content")
        assert result is not None
        assert result.read_text() == "My custom content"


class TestProjectGraphMerge:
    def test_merge_into_existing(self, tmp_path):
        from stratus.learning.artifacts import create_artifact

        # Create existing project graph
        graph_dir = tmp_path / ".ai-framework"
        graph_dir.mkdir(parents=True)
        existing = {"services": ["api"]}
        (graph_dir / "project-graph.json").write_text(json.dumps(existing))

        p = _make_proposal(
            type=ProposalType.PROJECT_GRAPH,
            title="Add db service",
            proposed_content=json.dumps({"services": ["db"], "version": "1.0"}),
        )
        result = create_artifact(p, tmp_path)
        assert result is not None
        data = json.loads(result.read_text())
        # Existing keys preserved, new keys merged
        assert "services" in data
        assert "version" in data

    def test_create_new_graph(self, tmp_path):
        from stratus.learning.artifacts import create_artifact

        p = _make_proposal(
            type=ProposalType.PROJECT_GRAPH,
            title="Init graph",
            proposed_content=json.dumps({"services": ["api"], "version": "1.0"}),
        )
        result = create_artifact(p, tmp_path)
        assert result is not None
        data = json.loads(result.read_text())
        assert data["services"] == ["api"]

    def test_atomic_write_uses_replace(self, tmp_path, monkeypatch):
        """Verify atomic write pattern: write to temp then os.replace."""
        from unittest.mock import patch

        from stratus.learning.artifacts import create_artifact

        p = _make_proposal(
            type=ProposalType.PROJECT_GRAPH,
            title="Atomic test",
            proposed_content=json.dumps({"key": "value"}),
        )
        os_replace = __import__("os").replace
        with patch(
            "stratus.learning.artifacts.os.replace", wraps=os_replace,
        ) as mock_replace:
            result = create_artifact(p, tmp_path)
        assert result is not None
        assert mock_replace.called
