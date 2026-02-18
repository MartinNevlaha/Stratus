"""Artifact content generators and file writer for accepted proposals."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from stratus.learning.models import Proposal, ProposalType


def _slug_from_title(title: str) -> str:
    """Convert a proposal title to a filesystem-safe slug."""
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug.strip())
    slug = re.sub(r"-{2,}", "-", slug)
    slug = slug.strip("-")
    if len(slug) > 60:
        slug = slug[:60].rstrip("-")
    return slug


def generate_artifact_content(
    proposal: Proposal, edited_content: str | None = None,
) -> str:
    """Return final content for the artifact file."""
    if edited_content is not None:
        return edited_content

    if proposal.type == ProposalType.RULE:
        return _generate_rule_content(proposal)
    if proposal.type == ProposalType.ADR:
        return _generate_adr_content(proposal)
    if proposal.type == ProposalType.TEMPLATE:
        return _generate_template_content(proposal)
    if proposal.type == ProposalType.SKILL:
        return _generate_skill_content(proposal)
    # PROJECT_GRAPH handled separately in create_artifact
    return proposal.proposed_content


def compute_artifact_path(proposal: Proposal, project_root: Path) -> Path:
    """Compute destination path based on ProposalType."""
    slug = _slug_from_title(proposal.title)
    if proposal.type == ProposalType.RULE:
        return project_root / ".claude" / "rules" / f"learning-{slug}.md"
    if proposal.type == ProposalType.ADR:
        return project_root / "docs" / "decisions" / f"{slug}.md"
    if proposal.type == ProposalType.TEMPLATE:
        return project_root / ".claude" / "templates" / f"{slug}.md"
    if proposal.type == ProposalType.PROJECT_GRAPH:
        return project_root / ".ai-framework" / "project-graph.json"
    if proposal.type == ProposalType.SKILL:
        return project_root / ".claude" / "skills" / slug / "prompt.md"
    return project_root / ".claude" / "rules" / f"learning-{slug}.md"


def create_artifact(
    proposal: Proposal, project_root: Path,
    edited_content: str | None = None,
) -> Path | None:
    """Write artifact to disk. Returns path on success, None on failure."""
    try:
        path = compute_artifact_path(proposal, project_root)

        if proposal.type == ProposalType.PROJECT_GRAPH:
            return _write_project_graph(proposal, path, edited_content)

        content = generate_artifact_content(proposal, edited_content)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path
    except Exception:
        return None


def _write_project_graph(
    proposal: Proposal, path: Path, edited_content: str | None,
) -> Path:
    """Atomic write for project-graph.json with merge semantics."""
    path.parent.mkdir(parents=True, exist_ok=True)

    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            existing = {}

    if edited_content is not None:
        new_data = json.loads(edited_content)
    else:
        new_data = json.loads(proposal.proposed_content)

    merged = {**existing, **new_data}

    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(merged, f, indent=2)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return path


def _generate_rule_content(proposal: Proposal) -> str:
    return f"""# {proposal.title}

{proposal.description}

## Rule

{proposal.proposed_content}
"""


def _generate_adr_content(proposal: Proposal) -> str:
    return f"""# {proposal.title}

## Status

Accepted (auto-generated from learning)

## Context

{proposal.description}

## Decision

{proposal.proposed_content}

## Consequences

This rule was detected from repeated patterns in the codebase.
"""


def _generate_template_content(proposal: Proposal) -> str:
    return f"""# {proposal.title}

{proposal.proposed_content}
"""


def _generate_skill_content(proposal: Proposal) -> str:
    return f"""# {proposal.title}

{proposal.description}

## Instructions

{proposal.proposed_content}
"""
