"""RulesIndex: load project rules, compute hashes, check immutability."""

from __future__ import annotations

import hashlib
from pathlib import Path

from stratus.rule_engine.invariants import FRAMEWORK_INVARIANTS
from stratus.rule_engine.models import (
    ImmutabilityViolation,
    Invariant,
    Rule,
    RuleSource,
    RulesSnapshot,
)


class RulesIndex:
    def __init__(
        self,
        project_root: Path,
        *,
        rules_dir: Path | None = None,
    ) -> None:
        self._project_root = project_root
        self._rules_dir = rules_dir or (project_root / ".claude" / "rules")
        self._snapshot: RulesSnapshot | None = None

    def load(self) -> RulesSnapshot:
        """Load all rules and compute hashes."""
        rules: list[Rule] = []

        # Load .claude/rules/*.md
        if self._rules_dir.is_dir():
            for md_file in sorted(self._rules_dir.glob("*.md")):
                content = md_file.read_text(encoding="utf-8")
                rules.append(
                    Rule(
                        name=md_file.stem,
                        source=RuleSource.PROJECT,
                        content=content,
                        path=str(md_file),
                        content_hash=_hash(content),
                    )
                )

        # Load CLAUDE.md
        claude_md = self._project_root / "CLAUDE.md"
        if claude_md.exists():
            content = claude_md.read_text(encoding="utf-8")
            rules.append(
                Rule(
                    name="CLAUDE",
                    source=RuleSource.CLAUDE_MD,
                    content=content,
                    path=str(claude_md),
                    content_hash=_hash(content),
                )
            )

        snapshot_hash = _hash("".join(r.content_hash for r in rules))
        self._snapshot = RulesSnapshot(rules=rules, snapshot_hash=snapshot_hash)
        return self._snapshot

    def check_immutability(
        self,
        previous: RulesSnapshot,
    ) -> list[ImmutabilityViolation]:
        """Compare current snapshot against previous. Return violations."""
        current = self.load()
        violations: list[ImmutabilityViolation] = []

        prev_map = {r.name: r for r in previous.rules}
        curr_map = {r.name: r for r in current.rules}

        for name in curr_map:
            if name not in prev_map:
                violations.append(
                    ImmutabilityViolation(
                        rule_name=name,
                        change_type="added",
                        details=f"Rule '{name}' was added",
                    )
                )

        for name in prev_map:
            if name not in curr_map:
                violations.append(
                    ImmutabilityViolation(
                        rule_name=name,
                        change_type="removed",
                        details=f"Rule '{name}' was removed",
                    )
                )

        for name in prev_map:
            if name in curr_map and prev_map[name].content_hash != curr_map[name].content_hash:
                violations.append(
                    ImmutabilityViolation(
                        rule_name=name,
                        change_type="modified",
                        details=f"Rule '{name}' content changed",
                    )
                )

        return violations

    def refresh(self) -> RulesSnapshot:
        """Force reload."""
        return self.load()

    def get_active_invariants(
        self,
        disabled_ids: list[str] | None = None,
    ) -> list[Invariant]:
        """Get active invariants, excluding disabled (except non-disablable)."""
        disabled = set(disabled_ids or [])
        return [inv for inv in FRAMEWORK_INVARIANTS if not inv.disablable or inv.id not in disabled]


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()
