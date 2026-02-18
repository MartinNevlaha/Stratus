"""Proposal generation, LLM prompt templates, and deduplication."""

from __future__ import annotations

import uuid
from pathlib import Path

from stratus.learning.config import LearningConfig
from stratus.learning.database import LearningDatabase
from stratus.learning.models import (
    DetectionType,
    PatternCandidate,
    Proposal,
    ProposalType,
)

_DETECTION_TO_PROPOSAL: dict[DetectionType, ProposalType] = {
    DetectionType.CODE_PATTERN: ProposalType.RULE,
    DetectionType.STRUCTURAL_CHANGE: ProposalType.TEMPLATE,
    DetectionType.FIX_PATTERN: ProposalType.RULE,
    DetectionType.IMPORT_PATTERN: ProposalType.RULE,
    DetectionType.CONFIG_PATTERN: ProposalType.RULE,
    DetectionType.SERVICE_DETECTED: ProposalType.PROJECT_GRAPH,
}


def _map_detection_to_proposal_type(detection_type: DetectionType) -> ProposalType:
    return _DETECTION_TO_PROPOSAL.get(detection_type, ProposalType.RULE)


def build_llm_prompt(candidate: PatternCandidate) -> str:
    """Build a structured prompt template for LLM assessment."""
    files_list = "\n".join(f"  - {f}" for f in candidate.files[:10])
    instances_text = ""
    for inst in candidate.instances[:5]:
        instances_text += f"  - {inst}\n"

    return f"""I detected the following recurring pattern in the codebase:

Pattern type: {candidate.detection_type}
Occurrences: {candidate.count} instances across {len(candidate.files)} files
Description: {candidate.description}

Files involved:
{files_list}

Example instances:
{instances_text}
Questions:
1. Is this a genuine, intentional pattern that should be codified?
2. What rule or guideline would you propose to formalize this pattern?
3. How confident are you that this is a real pattern (0.0-1.0)?
4. What exceptions or edge cases should the rule account for?
"""


def _check_existing_rules(candidate: PatternCandidate, rules_dir: Path) -> bool:
    """Check if a similar rule already exists in the rules directory."""
    if not rules_dir.exists():
        return False

    description_lower = candidate.description.lower()
    key_words = set(description_lower.split())
    # Remove common words
    stop_words = {
        "the", "a", "an", "in", "of", "and", "or",
        "is", "to", "for", "pattern", "repeated",
    }
    key_words -= stop_words

    for rule_file in rules_dir.glob("*.md"):
        try:
            content = rule_file.read_text().lower()
            # Check if enough key words match
            matches = sum(1 for w in key_words if w in content)
            if key_words and matches / len(key_words) > 0.5:
                return True
        except OSError:
            continue
    return False


class ProposalGenerator:
    def __init__(self, config: LearningConfig, db: LearningDatabase) -> None:
        self._config = config
        self._db = db

    def generate_proposals(
        self,
        candidates: list[PatternCandidate],
        *,
        rules_dir: Path | None = None,
        project_root: Path | None = None,
    ) -> list[Proposal]:
        """Generate proposals from scored candidates."""
        if not candidates:
            return []

        proposals: list[Proposal] = []
        seen_hashes: set[str] = set()

        for candidate in candidates:
            # Deduplication by description hash
            desc_hash = candidate.description_hash or ""
            if desc_hash in seen_hashes:
                continue
            seen_hashes.add(desc_hash)

            # Skip if a similar rule already exists
            if rules_dir and _check_existing_rules(candidate, rules_dir):
                continue

            proposal_type = _map_detection_to_proposal_type(candidate.detection_type)
            prompt_content = build_llm_prompt(candidate)

            proposal = Proposal(
                id=str(uuid.uuid4()),
                candidate_id=candidate.id,
                type=proposal_type,
                title=_generate_title(candidate),
                description=candidate.description,
                proposed_content=prompt_content,
                confidence=candidate.confidence_final,
            )

            # Set proposed_path if project_root is available
            if project_root:
                from stratus.learning.artifacts import compute_artifact_path

                proposal.proposed_path = str(
                    compute_artifact_path(proposal, project_root),
                )

            proposals.append(proposal)

            if len(proposals) >= self._config.max_proposals_per_session:
                break

        return proposals


def _generate_title(candidate: PatternCandidate) -> str:
    """Generate a concise proposal title from the candidate."""
    type_prefix = {
        DetectionType.CODE_PATTERN: "Add rule",
        DetectionType.STRUCTURAL_CHANGE: "Add template",
        DetectionType.FIX_PATTERN: "Add guideline",
        DetectionType.IMPORT_PATTERN: "Standardize imports",
        DetectionType.CONFIG_PATTERN: "Add config rule",
        DetectionType.SERVICE_DETECTED: "Update project graph",
    }
    prefix = type_prefix.get(candidate.detection_type, "Add rule")
    # Truncate description for title
    desc = candidate.description
    if len(desc) > 50:
        desc = desc[:47] + "..."
    return f"{prefix}: {desc}"
