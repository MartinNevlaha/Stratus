"""Framework invariants — hard constraints on agent and framework behavior."""

from __future__ import annotations

from stratus.rule_engine.models import Invariant, InvariantContext, InvariantViolation

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

_SOFT_LIMIT = 300
_HARD_LIMIT = 500


def _check_file_size(context: InvariantContext) -> list[InvariantViolation]:
    """Check *.py files under project_root/src for line count violations."""
    violations: list[InvariantViolation] = []
    if context.project_root is None:
        return violations

    src_dir = context.project_root / "src"
    if not src_dir.is_dir():
        return violations

    for py_file in src_dir.rglob("*.py"):
        name = py_file.name
        if name.startswith("test_") or name == "__init__.py":
            continue
        lines = len(py_file.read_text(encoding="utf-8").splitlines())
        if lines > _HARD_LIMIT:
            violations.append(
                InvariantViolation(
                    invariant_id="inv-file-size-limit",
                    message=f"{py_file.name}: {lines} lines exceeds hard limit of {_HARD_LIMIT}",
                    file_path=str(py_file),
                )
            )
        elif lines > _SOFT_LIMIT:
            violations.append(
                InvariantViolation(
                    invariant_id="inv-file-size-limit",
                    message=f"{py_file.name}: {lines} lines exceeds soft limit of {_SOFT_LIMIT}",
                    file_path=str(py_file),
                )
            )

    return violations


def _check_rules_immutable(context: InvariantContext) -> list[InvariantViolation]:
    """Check that no rules changed since the previous snapshot."""
    if not context.spec_active or context.previous_rules_snapshot is None:
        return []
    if context.project_root is None:
        return []

    from stratus.rule_engine.index import RulesIndex

    immutability_violations = RulesIndex(context.project_root).check_immutability(
        context.previous_rules_snapshot
    )
    return [
        InvariantViolation(
            invariant_id="inv-rules-immutable-in-spec",
            message=v.details,
            file_path=None,
        )
        for v in immutability_violations
    ]


_HANDLERS = {
    "inv-file-size-limit": _check_file_size,
    "inv-rules-immutable-in-spec": _check_rules_immutable,
}


def validate_against_invariants(
    invariants: list[Invariant],
    context: InvariantContext | None = None,
) -> list[InvariantViolation]:
    """Validate framework state against active invariants.

    Returns list of InvariantViolation objects. Returns [] when context is None
    (backward-compatible with the original stub).
    """
    if context is None:
        return []

    disabled = set(context.disabled_ids)
    violations: list[InvariantViolation] = []

    for inv in invariants:
        # Respect disablable flag: non-disablable invariants always run
        if inv.disablable and inv.id in disabled:
            continue

        handler = _HANDLERS.get(inv.id)
        if handler is None:
            continue  # documented-only invariant, no runtime check

        violations.extend(handler(context))

    return violations
