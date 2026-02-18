---
description: Analyze a Claude Code JSONL transcript for token usage and compaction events
---

Analyze a transcript file:

```bash
stratus analyze $ARGUMENTS
```

Parses the JSONL transcript and displays message count, peak/final token usage, context utilization percentage, and compaction events with timestamps and triggers.

Options:
- `--context-window <tokens>` — context window size (default: 200000)
