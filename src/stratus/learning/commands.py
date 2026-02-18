"""CLI command handler for learning engine operations."""

from __future__ import annotations

import argparse
from pathlib import Path


def cmd_learning(args: argparse.Namespace) -> None:
    """Handle learning subcommand actions."""
    from stratus.learning.config import load_learning_config
    from stratus.learning.database import LearningDatabase
    from stratus.learning.models import Decision
    from stratus.learning.watcher import ProjectWatcher

    action = args.learning_action
    config = load_learning_config(None)
    db = LearningDatabase()

    if action == "status":
        s, state = db.stats(), db.get_analysis_state()
        print(
            f"Learning Status:\n  Enabled: {config.global_enabled}"
            f"\n  Sensitivity: {config.sensitivity}"
            f"\n  Candidates: {s['candidates_total']}"
            f"\n  Proposals: {s['proposals_total']}"
            f"\n  Last commit: {state.get('last_commit', 'none')}"
            f"\n  Total analyzed: {state.get('total_commits_analyzed', 0)}"
        )

    elif action == "analyze":
        watcher = ProjectWatcher(config=config, db=db, project_root=Path.cwd())
        result = watcher.analyze_changes(
            since_commit=getattr(args, "since", None),
            scope=getattr(args, "scope", None),
        )
        print(f"Detections:  {len(result.detections)}")
        print(f"Commits:     {result.analyzed_commits}")
        print(f"Time:        {result.analysis_time_ms}ms")

    elif action == "proposals":
        max_count = getattr(args, "max_count", 10)
        min_conf = getattr(args, "min_confidence", 0.0)
        proposals = db.list_proposals(min_confidence=min_conf, limit=max_count)
        if not proposals:
            print("No pending proposals.")
        else:
            for p in proposals:
                print(f"  [{p.id[:8]}] {p.title} (confidence: {p.confidence:.2f})")

    elif action == "decide":
        proposal_id = args.proposal_id
        decision = Decision(args.decision)
        db.decide_proposal(proposal_id, decision)
        print(f"Decided: {proposal_id} -> {decision.value}")

    elif action == "config":
        if getattr(args, "enable", False):
            print("Learning enabled (runtime only — set in .ai-framework.json for persistence)")
        elif getattr(args, "disable", False):
            print("Learning disabled (runtime only)")
        else:
            c = config
            print(
                f"  global_enabled: {c.global_enabled}\n  sensitivity: {c.sensitivity}"
                f"\n  min_confidence: {c.min_confidence}\n  cooldown_days: {c.cooldown_days}"
                f"\n  max_proposals/ses: {c.max_proposals_per_session}"
                f"\n  batch_frequency: {c.batch_frequency}"
                f"\n  commit_threshold: {c.commit_batch_threshold}"
                f"\n  min_age_hours: {c.min_age_hours}"
            )

    db.close()
