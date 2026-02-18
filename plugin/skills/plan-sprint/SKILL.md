---
name: plan-sprint
description: "Break down work into tasks with dependencies and resource allocation"
agent: delivery-tpm
context: fork
---

Plan a sprint for: "$ARGUMENTS"

1. Read the provided requirements or user stories from "$ARGUMENTS" or ask the user to paste them.
2. Break each story into implementable tasks no larger than one day of work.
3. Identify dependencies between tasks and mark which must be completed before others can start.
4. Estimate relative complexity for each task using story points (1, 2, 3, 5, 8).
5. Assign each task to an appropriate engineering role: backend, frontend, infra, QA, or docs.
6. Flag tasks that are blocked on external decisions or missing information.
7. Identify the critical path — the sequence of dependent tasks that determines minimum sprint duration.
8. Produce a task list grouped by engineering role.

Output format:
- Section "Task List" — table with columns: ID, Title, Role, Points, Depends On, Blocked By
- Section "Critical Path" — ordered sequence of task IDs with total point estimate
- Section "Blockers" — items requiring resolution before sprint can start
- Section "Definition of Done" — shared checklist applicable to all tasks
