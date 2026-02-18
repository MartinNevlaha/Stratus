---
name: create-architecture
description: "Design system architecture and create Architecture Decision Records"
agent: delivery-strategic-architect
context: fork
---

Design the architecture for: "$ARGUMENTS"

1. Read `docs/architecture/framework-architecture.md` to understand existing subsystem boundaries.
2. Identify which existing components are affected and how interfaces will change.
3. Evaluate at least two technology or design alternatives for each key decision point.
4. For each decision, produce an Architecture Decision Record (ADR) with sections:
   - Status (Proposed)
   - Context — the problem being solved
   - Decision — the chosen approach
   - Consequences — trade-offs, risks, and benefits
5. Create a component diagram in fenced markdown code blocks using ASCII art or Mermaid syntax.
6. Define explicit interfaces between new and existing services (method signatures, data shapes).
7. Identify data flow paths and state ownership for each new component.
8. Flag any breaking changes to existing APIs or database schemas.

Output format:
- Section "Component Diagram" — Mermaid or ASCII diagram
- Section "ADRs" — one subsection per decision
- Section "Interface Definitions" — typed signatures per boundary
- Section "Migration Notes" — breaking changes and rollout sequence
