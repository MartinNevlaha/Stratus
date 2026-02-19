"""ProjectWatcher facade: orchestrates the full learning pipeline."""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from stratus.learning.ast_analyzer import (
    extract_python_patterns,
    find_repeated_patterns,
)
from stratus.learning.config import LearningConfig
from stratus.learning.database import LearningDatabase
from stratus.learning.git_analyzer import GitAnalyzer
from stratus.learning.heuristics import run_heuristics
from stratus.learning.models import (
    AnalysisResult,
    Decision,
    Detection,
    Proposal,
    ProposalStatus,
)
from stratus.learning.proposals import ProposalGenerator


class ProjectWatcher:
    def __init__(
        self,
        config: LearningConfig,
        db: LearningDatabase,
        project_root: Path,
    ) -> None:
        self._config = config
        self._db = db
        self._root = project_root

    def analyze_changes(
        self,
        since_commit: str | None = None,
        scope: str | None = None,
    ) -> AnalysisResult:
        """Run full analysis pipeline: git → AST → heuristics → proposals."""
        # Warmup guard: skip analysis if DB is too young
        if self._config.min_age_hours > 0:
            created = self._db.get_db_creation_time()
            if created:
                from datetime import UTC, datetime

                age = datetime.now(UTC) - datetime.fromisoformat(created)
                if age.total_seconds() < self._config.min_age_hours * 3600:
                    return AnalysisResult(
                        detections=[],
                        analyzed_commits=0,
                        analysis_time_ms=0,
                    )

        start_ms = time.monotonic_ns() // 1_000_000

        git_analyzer = GitAnalyzer(self._root)

        # Step 1: Git analysis → raw detections
        git_detections = git_analyzer.analyze_changes(
            since_commit=since_commit,
            scope=scope,
        )
        commit_count = git_analyzer._get_commits_since(since_commit)

        # Step 2: AST analysis → code pattern detections
        # (only for Python files in git detections)
        ast_detections = self._run_ast_analysis(git_detections)

        all_detections = git_detections + ast_detections

        # Step 3: Heuristics → scored candidates
        candidates = run_heuristics(
            all_detections,
            self._db,
            cooldown_days=self._config.cooldown_days,
        )

        # Step 4: Save candidates
        for candidate in candidates:
            self._db.save_candidate(candidate)

        # Step 5: Generate proposals
        generator = ProposalGenerator(self._config, self._db)
        proposals = generator.generate_proposals(
            candidates,
            rules_dir=self._root / ".claude" / "rules",
            project_root=self._root,
        )

        # Step 6: Save proposals
        for proposal in proposals:
            self._db.save_proposal(proposal)

        # Step 7: Update analysis state
        last_commit = since_commit or ""
        self._db.update_analysis_state(last_commit, commit_count)

        elapsed_ms = (time.monotonic_ns() // 1_000_000) - start_ms
        return AnalysisResult(
            detections=all_detections,
            analyzed_commits=commit_count,
            analysis_time_ms=elapsed_ms,
        )

    def _run_ast_analysis(self, git_detections: list[Detection]) -> list[Detection]:
        """Extract AST patterns from Python files mentioned in detections."""
        python_files: set[str] = set()
        for d in git_detections:
            for f in d.files:
                if f.endswith(".py"):
                    python_files.add(f)

        if not python_files:
            return []

        patterns_by_file: dict[str, dict] = {}
        for filepath in python_files:
            full_path = self._root / filepath
            try:
                source = full_path.read_text()
                patterns_by_file[filepath] = extract_python_patterns(source)
            except OSError:
                continue

        return find_repeated_patterns(patterns_by_file)

    def get_proposals(
        self,
        max_count: int = 3,
        min_confidence: float = 0.0,
    ) -> list[Proposal]:
        """Get pending proposals from the database."""
        return self._db.list_proposals(
            status=ProposalStatus.PENDING,
            min_confidence=min_confidence,
            limit=max_count,
        )

    def decide_proposal(
        self,
        proposal_id: str,
        decision: Decision,
        edited_content: str | None = None,
    ) -> dict:
        """Record a decision on a proposal, create artifact on accept, save memory event."""
        self._db.decide_proposal(proposal_id, decision, edited_content)

        artifact_path = None
        if decision == Decision.ACCEPT:
            proposal = self._db.get_proposal(proposal_id)
            if proposal:
                from stratus.learning.artifacts import create_artifact

                artifact_path = create_artifact(
                    proposal,
                    self._root,
                    edited_content,
                )
                self._snapshot_rule_baseline(proposal, artifact_path)

        # Save memory event (best-effort)
        self._save_memory_event(proposal_id, decision, artifact_path)

        return {
            "proposal_id": proposal_id,
            "decision": decision.value,
            "artifact_path": str(artifact_path) if artifact_path else None,
        }

    def _snapshot_rule_baseline(self, proposal: Proposal, artifact_path: object) -> None:
        """Best-effort: snapshot the failure baseline for a newly accepted rule."""
        if artifact_path is None:
            return
        try:
            from stratus.learning.analytics import snapshot_baseline
            from stratus.learning.models import FailureCategory

            _TYPE_TO_CATEGORY: dict[str, FailureCategory] = {
                "rule": FailureCategory.LINT_ERROR,
                "adr": FailureCategory.REVIEW_FAILURE,
                "template": FailureCategory.LINT_ERROR,
                "skill": FailureCategory.MISSING_TEST,
                "project_graph": FailureCategory.LINT_ERROR,
            }
            category = _TYPE_TO_CATEGORY.get(proposal.type, FailureCategory.LINT_ERROR)
            snapshot_baseline(
                self._db.analytics,
                proposal.id,
                str(artifact_path),
                category,
            )
        except Exception:
            pass

    def _save_memory_event(
        self,
        proposal_id: str,
        decision: Decision,
        artifact_path: Path | None = None,
    ) -> None:
        """Save an enriched memory event for the decision (best-effort)."""
        from stratus.hooks._common import get_api_url

        proposal = self._db.get_proposal(proposal_id)
        title = proposal.title if proposal else f"proposal {proposal_id}"
        proposal_type = proposal.type if proposal else "unknown"
        refs: dict = {"proposal_id": proposal_id}
        if artifact_path:
            refs["artifacts"] = [str(artifact_path)]

        event_type = "learning_decision" if decision == Decision.ACCEPT else "rejected_pattern"

        try:
            api_url = get_api_url()
            httpx.post(
                f"{api_url}/api/memory/save",
                json={
                    "text": f"Learning decision: {decision.value} — {title}",
                    "type": event_type,
                    "actor": "hook",
                    "tags": ["learning", decision.value, proposal_type],
                    "importance": 0.7 if decision == Decision.ACCEPT else 0.5,
                    "refs": refs,
                },
                timeout=2.0,
            )
        except Exception:
            pass  # Non-blocking: failures are silently ignored
