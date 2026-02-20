"""Classic dispatch engine: phase briefings, role mapping, task assignment."""

from __future__ import annotations

from pathlib import Path

from stratus.orchestration.delivery_coordinator import PHASE_LEADS, PHASE_ROLES
from stratus.orchestration.delivery_models import DeliveryPhase, DeliveryState

_AGENT_PREFIX = "delivery-"

PHASE_DESCRIPTIONS: dict[DeliveryPhase, str] = {
    DeliveryPhase.DISCOVERY: (
        "Understand the problem space, gather requirements, identify stakeholders."
    ),
    DeliveryPhase.ARCHITECTURE: (
        "Design system architecture, evaluate trade-offs, define contracts."
    ),
    DeliveryPhase.PLANNING: "Break work into tasks, estimate scope, assign ownership.",
    DeliveryPhase.IMPLEMENTATION: (
        "Build features following the plan. TDD, small PRs, continuous integration."
    ),
    DeliveryPhase.QA: "Verify correctness via tests, code review, and integration checks.",
    DeliveryPhase.GOVERNANCE: "Security audit, compliance review, risk assessment.",
    DeliveryPhase.PERFORMANCE: "Benchmark, profile, optimize. Validate against SLAs.",
    DeliveryPhase.RELEASE: "Prepare release artifacts, documentation, deployment pipeline.",
    DeliveryPhase.LEARNING: "Retrospective: capture lessons learned, update rules and patterns.",
}

PHASE_OBJECTIVES: dict[DeliveryPhase, list[str]] = {
    DeliveryPhase.DISCOVERY: [
        "Identify all stakeholders and their needs",
        "Document functional and non-functional requirements",
        "Produce a discovery summary for architecture phase",
    ],
    DeliveryPhase.ARCHITECTURE: [
        "Produce architecture decision records (ADRs)",
        "Define API contracts and data models",
        "Identify cross-cutting concerns (auth, logging, errors)",
    ],
    DeliveryPhase.PLANNING: [
        "Create task breakdown with clear acceptance criteria",
        "Assign tasks to appropriate roles",
        "Identify dependencies and critical path",
    ],
    DeliveryPhase.IMPLEMENTATION: [
        "Implement all planned tasks following TDD",
        "Keep each change small and reviewable",
        "All tests passing before advancing",
    ],
    DeliveryPhase.QA: [
        "All unit and integration tests pass",
        "Code review completed with no must_fix findings",
        "E2E workflows verified",
    ],
    DeliveryPhase.GOVERNANCE: [
        "Security review completed",
        "No critical or high-severity findings",
        "Compliance requirements satisfied",
    ],
    DeliveryPhase.PERFORMANCE: [
        "Benchmarks meet defined SLAs",
        "No regressions from baseline",
        "Optimization opportunities documented",
    ],
    DeliveryPhase.RELEASE: [
        "Release notes and changelog prepared",
        "Deployment pipeline validated",
        "Documentation updated",
    ],
    DeliveryPhase.LEARNING: [
        "Retrospective completed",
        "Lessons captured as rules or patterns",
        "Process improvements identified",
    ],
}

# Phase order for "next phase" hints
_PHASE_ORDER: list[DeliveryPhase] = list(DeliveryPhase)

_FIX_LOOP_PHASES = {DeliveryPhase.QA, DeliveryPhase.GOVERNANCE, DeliveryPhase.PERFORMANCE}


def _compute_role_keywords(
    project_root: Path | None = None,
) -> dict[str, list[str]]:
    """Compute _ROLE_KEYWORDS from the agent registry."""
    from stratus.registry.loader import AgentRegistry

    registry = AgentRegistry.load_merged(project_root)
    result: dict[str, list[str]] = {}
    for agent in registry.filter_by_mode("default"):
        if not agent.keywords:
            continue
        # Use short name (strip delivery- prefix)
        name = agent.name
        if name.startswith("delivery-"):
            name = name[len("delivery-") :]
        result[name] = agent.keywords
    return result


_ROLE_KEYWORDS: dict[str, list[str]] = _compute_role_keywords()


def role_to_agent_name(role: str) -> str:
    """'backend-engineer' -> 'delivery-backend-engineer'."""
    if role.startswith(_AGENT_PREFIX):
        return role
    return f"{_AGENT_PREFIX}{role}"


def suggest_role_for_task(description: str, available_roles: list[str]) -> str | None:
    """Keyword heuristic: match task description to best role."""
    desc_lower = description.lower()
    best_role: str | None = None
    best_score = 0

    for role, keywords in _ROLE_KEYWORDS.items():
        if role not in available_roles:
            continue
        score = sum(1 for kw in keywords if kw in desc_lower)
        if score > best_score:
            best_score = score
            best_role = role

    return best_role


class DeliveryDispatcher:
    """Stateless prompt generation for classic dispatch mode."""

    def build_phase_briefing(self, state: DeliveryState) -> str:
        """Markdown briefing: phase, lead, agents, objectives, next hint."""
        phase = state.delivery_phase
        lead = state.phase_lead or PHASE_LEADS.get(phase, "unknown")
        roles = state.active_roles or PHASE_ROLES.get(phase, [])
        desc = PHASE_DESCRIPTIONS.get(phase, "")
        objectives = PHASE_OBJECTIVES.get(phase, [])

        lines = [
            f"## Phase: {phase.value.upper()}",
            "",
            desc,
            "",
            f"**Lead agent:** `{role_to_agent_name(lead)}`",
            "",
            "### Active Agents",
            "",
        ]
        for role in roles:
            marker = " (lead)" if role == lead else ""
            lines.append(f"- `{role_to_agent_name(role)}`{marker}")

        if objectives:
            lines.append("")
            lines.append("### Objectives")
            lines.append("")
            for obj in objectives:
                lines.append(f"- {obj}")

        if state.plan_path:
            lines.append("")
            lines.append(f"**Plan:** {state.plan_path}")

        # Next phase hint
        lines.append("")
        idx = _PHASE_ORDER.index(phase)
        if idx < len(_PHASE_ORDER) - 1:
            next_phase = _PHASE_ORDER[idx + 1]
            lines.append(f"**Next phase:** {next_phase.value}")
        else:
            lines.append("**This is the final phase.** Complete delivery when done.")

        return "\n".join(lines)

    def build_task_assignments(self, state: DeliveryState, tasks: list[dict[str, str]]) -> str:
        """Markdown table: Task | Suggested Agent | Rationale."""
        roles = state.active_roles or PHASE_ROLES.get(state.delivery_phase, [])

        if not tasks:
            return "No tasks to assign."

        lines = [
            "| Task | Suggested Agent | Rationale |",
            "|------|----------------|-----------|",
        ]
        for task in tasks:
            tid = task.get("id", "?")
            desc = task.get("description", "")
            role = suggest_role_for_task(desc, roles)
            if role:
                agent = role_to_agent_name(role)
                rationale = f"Keywords match `{role}`"
            else:
                # Fall back to phase lead, then first available role
                lead = state.phase_lead or PHASE_LEADS.get(state.delivery_phase)
                if lead and lead in roles:
                    agent = role_to_agent_name(lead)
                    rationale = "Fallback to phase lead"
                elif roles:
                    agent = role_to_agent_name(roles[0])
                    rationale = "Fallback to first available role"
                else:
                    agent = role_to_agent_name("tpm")
                    rationale = "Fallback to TPM"
            lines.append(f"| {tid}: {desc} | `{agent}` | {rationale} |")

        return "\n".join(lines)

    def build_delegation_prompt(self, state: DeliveryState, task: dict[str, str], role: str) -> str:
        """Template for Task tool delegation."""
        agent = role_to_agent_name(role)
        tid = task.get("id", "?")
        desc = task.get("description", "")

        lines = [
            f"Delegate to agent `{agent}` (subagent_type: delivery-implementation-expert).",
            "",
            f"**Task {tid}:** {desc}",
            f"**Spec slug:** {state.slug}",
            f"**Phase:** {state.delivery_phase.value}",
        ]
        if state.plan_path:
            lines.append(f"**Plan:** {state.plan_path}")

        lines.append("")
        lines.append(
            "Follow TDD. Run tests after completion."
            + " Report back with files changed and test results."
        )
        return "\n".join(lines)

    def build_completion_summary(self, state: DeliveryState) -> str:
        """Phase results summary + advance/fix-loop suggestion."""
        phase = state.delivery_phase
        lines = [f"## Phase {phase.value.upper()} — Completion Summary", ""]

        idx = _PHASE_ORDER.index(phase)
        if phase in _FIX_LOOP_PHASES:
            lines.append(
                f"Review iteration: {state.review_iteration}/{state.max_review_iterations}"
            )
            lines.append("")
            lines.append("**Options:**")
            lines.append("- **Advance** — move to next phase if all checks pass")
            lines.append("- **Fix loop** — return to implementation to address findings")
        elif idx < len(_PHASE_ORDER) - 1:
            next_phase = _PHASE_ORDER[idx + 1]
            lines.append(f"Ready to advance to **{next_phase.value}**.")
        else:
            lines.append("Delivery is complete. Run `/api/delivery/complete` to finalize.")

        return "\n".join(lines)

    def build_dispatch_context(self, state: DeliveryState) -> dict[str, object]:
        """Serializable dict for routes/MCP."""
        phase = state.delivery_phase
        roles = state.active_roles or PHASE_ROLES.get(phase, [])
        lead = state.phase_lead or PHASE_LEADS.get(phase)

        agents: list[dict[str, object]] = []
        for role in roles:
            agents.append(
                {
                    "role": role,
                    "agent_name": role_to_agent_name(role),
                    "is_lead": role == lead,
                }
            )

        return {
            "phase": phase.value,
            "slug": state.slug,
            "lead_agent": role_to_agent_name(lead) if lead else None,
            "agents": agents,
            "objectives": PHASE_OBJECTIVES.get(phase, []),
            "briefing_markdown": self.build_phase_briefing(state),
        }
