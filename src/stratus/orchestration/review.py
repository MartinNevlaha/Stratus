"""Review verdict parsing and aggregation utilities."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime

from stratus.orchestration.models import (
    FindingSeverity,
    ReviewFinding,
    ReviewVerdict,
    SpecState,
    Verdict,
)

# Matches: "Verdict: PASS" or "Verdict: FAIL" (case-insensitive)
_VERDICT_RE = re.compile(r"verdict\s*:\s*(pass|fail)", re.IGNORECASE)

# Matches: "- must_fix: ..." or "- should_fix: ..." or "- suggestion: ..."
_FINDING_RE = re.compile(
    r"^\s*-\s*(must_fix|should_fix|suggestion)\s*:\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)

# Matches a file path with optional line number at the start of finding body.
# e.g. "src/app.py:42 — description" or "src/models.py — description"
_FILE_RE = re.compile(
    r"^([\w./\\-]+\.\w+)(?::(\d+))?\s*(?:—|--)?\s*(.*)"
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _parse_finding(severity_str: str, body: str) -> ReviewFinding:
    """Parse a single finding body into a ReviewFinding."""
    body = body.strip()
    severity = FindingSeverity(severity_str.lower())

    m = _FILE_RE.match(body)
    if m:
        file_path = m.group(1)
        line = int(m.group(2)) if m.group(2) else None
        description = m.group(3).strip() or body
    else:
        file_path = ""
        line = None
        description = body

    return ReviewFinding(
        file_path=file_path,
        line=line,
        severity=severity,
        description=description,
    )


def parse_verdict(reviewer_output: str, reviewer_name: str) -> ReviewVerdict:
    """Parse reviewer agent output into a ReviewVerdict.

    Searches for "Verdict: PASS/FAIL" (case-insensitive).
    Defaults to FAIL when no verdict line is found.
    """
    verdict_match = _VERDICT_RE.search(reviewer_output)
    if verdict_match:
        verdict = Verdict.PASS if verdict_match.group(1).lower() == "pass" else Verdict.FAIL
    else:
        verdict = Verdict.FAIL

    findings: list[ReviewFinding] = []
    for finding_match in _FINDING_RE.finditer(reviewer_output):
        severity_str = finding_match.group(1)
        body = finding_match.group(2)
        findings.append(_parse_finding(severity_str, body))

    return ReviewVerdict(
        reviewer=reviewer_name,
        verdict=verdict,
        findings=findings,
        raw_output=reviewer_output,
    )


def aggregate_verdicts(verdicts: list[ReviewVerdict]) -> dict:
    """Aggregate a list of ReviewVerdicts into a summary dict."""
    failed_reviewers: list[str] = []
    must_fix_count = 0
    should_fix_count = 0
    total_findings = 0

    for v in verdicts:
        if v.verdict == Verdict.FAIL:
            failed_reviewers.append(v.reviewer)
        for f in v.findings:
            total_findings += 1
            if f.severity == FindingSeverity.MUST_FIX:
                must_fix_count += 1
            elif f.severity == FindingSeverity.SHOULD_FIX:
                should_fix_count += 1

    return {
        "all_passed": len(failed_reviewers) == 0,
        "failed_reviewers": failed_reviewers,
        "total_findings": total_findings,
        "must_fix_count": must_fix_count,
        "should_fix_count": should_fix_count,
    }


def build_fix_instructions(verdicts: list[ReviewVerdict]) -> str:
    """Build markdown fix instructions grouped by file path.

    Returns an empty string when there are no findings.
    """
    # Collect all findings from verdicts that have any
    grouped: dict[str, list[ReviewFinding]] = defaultdict(list)
    for v in verdicts:
        for f in v.findings:
            grouped[f.file_path].append(f)

    if not grouped:
        return ""

    lines: list[str] = []
    for file_path, findings in grouped.items():
        lines.append(f"## {file_path}")
        for f in findings:
            line_part = f" line {f.line}:" if f.line is not None else ""
            lines.append(f"- [{f.severity}]{line_part} {f.description}")
        lines.append("")

    return "\n".join(lines).rstrip()


def should_continue_review_loop(spec_state: SpecState) -> bool:
    """Return True when another review iteration is allowed."""
    return spec_state.review_iteration < spec_state.max_review_iterations


def advance_review_iteration(spec_state: SpecState) -> SpecState:
    """Return a new SpecState with review_iteration incremented by one."""
    return spec_state.model_copy(
        update={
            "review_iteration": spec_state.review_iteration + 1,
            "last_updated": _now_iso(),
        }
    )
