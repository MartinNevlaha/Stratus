---
name: run-discovery
description: "Analyze requirements and break down user stories into actionable tasks"
agent: delivery-product-owner
context: fork
---

Run a discovery session for: "$ARGUMENTS"

1. Gather requirements by asking the user clarifying questions about goals, constraints, and success criteria.
2. Read the codebase structure using `Glob` and `Read` to identify existing patterns relevant to the request.
3. Identify stakeholders and affected subsystems from `docs/architecture/framework-architecture.md`.
4. List assumptions and open questions that must be resolved before implementation begins.
5. Decompose the work into user stories using the format: "As a <role>, I want <feature> so that <benefit>."
6. For each story, define acceptance criteria as a checklist of verifiable conditions.
7. Assign a relative complexity estimate (XS/S/M/L/XL) to each story based on scope.
8. Produce a prioritized backlog ordered by business value and dependency order.

Output format:
- Section "Assumptions" — bulleted list
- Section "Open Questions" — numbered list
- Section "User Stories" — numbered, each with acceptance criteria and estimate
- Section "Recommended Priority Order" — story numbers with rationale
