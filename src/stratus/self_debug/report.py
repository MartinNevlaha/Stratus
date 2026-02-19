"""Markdown report formatter for self-debug sandbox."""

from __future__ import annotations

from stratus.self_debug.models import DebugReport, PatchProposal


def format_report(report: DebugReport) -> str:
    """Produce structured markdown report from DebugReport."""
    sections: list[str] = []

    sections.append("# Self-Debug Report\n")
    sections.append("## Summary\n")
    sections.append(f"- **Files analyzed:** {report.analyzed_files}")
    sections.append(f"- **Files skipped:** {report.skipped_files}")
    sections.append(f"- **Issues found:** {len(report.issues)}")
    sections.append(f"- **Patches generated:** {len(report.patches)}")
    sections.append(f"- **Analysis time:** {report.analysis_time_ms}ms")
    sections.append("")

    if not report.issues:
        sections.append("No issues found.\n")
        return "\n".join(sections)

    patches_by_issue: dict[str, PatchProposal] = {p.issue_id: p for p in report.patches}

    sections.append("## Issues\n")
    for i, issue in enumerate(report.issues, 1):
        sections.append(f"### {i}. [{issue.type.value}] {issue.file_path}:{issue.line_start}\n")
        sections.append(f"**Description:** {issue.description}\n")
        sections.append(f"**Suggestion:** {issue.suggestion}\n")

        patch = patches_by_issue.get(issue.id)
        if patch:
            sections.append(f"**Risk:** {patch.risk.value}")
            sections.append(f"**Governance impact:** {patch.governance_impact.value}\n")
            sections.append("**Patch:**\n")
            sections.append(f"```diff\n{patch.unified_diff}```\n")
            if patch.tests_affected:
                sections.append("**Affected tests:**\n")
                for t in patch.tests_affected:
                    sections.append(f"- {t}")
                sections.append("")
        else:
            sections.append("*No patch generated — report-only.*\n")

    return "\n".join(sections)
