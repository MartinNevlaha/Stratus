---
description: Accept, reject, or ignore a learning proposal
---

Decide on a proposal:

```bash
stratus learning decide $ARGUMENTS
```

Takes a proposal ID and a decision (accept, reject, ignore, snooze).

- `accept` — creates the artifact (rule, ADR, template, or skill) and records a memory event
- `reject` — applies a 7-day cooldown and lowers the prior decision factor
- `ignore` — same as reject but with lower impact on future scoring
- `snooze` — defers the proposal without affecting scoring

Example:
```bash
stratus learning decide abc123 accept
```
