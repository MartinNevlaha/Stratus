"""Framework invariants — hard constraints on agent and framework behavior."""

from __future__ import annotations

from stratus.rule_engine.models import Invariant

FRAMEWORK_INVARIANTS: list[Invariant] = [
    Invariant(
        id="inv-process-no-code",
        title="Process roles never write code",
        content="Process roles NEVER use Write/Edit tools.",
        disablable=True,
    ),
    Invariant(
        id="inv-reviewers-readonly",
        title="Reviewers never modify code",
        content="Reviewer agents produce PASS/FAIL verdicts only.",
        disablable=True,
    ),
    Invariant(
        id="inv-engineering-quality-gates",
        title="Engineering roles never bypass quality gates",
        content="All code must pass tests/lint/review before merge.",
        disablable=True,
    ),
    Invariant(
        id="inv-no-new-deps",
        title="No new runtime dependencies without approval",
        content="No new deps without user approval.",
        disablable=True,
    ),
    Invariant(
        id="inv-file-size-limit",
        title="Production files under 300 lines",
        content="500 is hard limit. Test files exempt.",
        disablable=True,
    ),
    Invariant(
        id="inv-rules-immutable-in-spec",
        title="Rules immutable during active specs",
        content="No rule changes during active swarm specs.",
        disablable=False,
    ),
]


def validate_against_invariants(_invariants: list[Invariant]) -> list[str]:
    """Validate framework state against active invariants. Returns list of violation messages."""
    # Placeholder — actual validation happens in the coordinator/hooks layer
    # where context about what is happening is available.
    return []
