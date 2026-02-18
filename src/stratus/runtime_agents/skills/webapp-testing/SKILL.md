---
name: webapp-testing
description: Test local web applications using Playwright. Use when verifying UI behavior, testing user flows, checking screenshots, or debugging browser-rendered output.
context: fork
agent: qa-engineer
---

# Web Application Testing

Test the web application using playwright-cli for browser automation.

## Decision Tree

```
Is the server already running?
├─ No → Start it first (npm run dev / uv run ... / etc.)
└─ Yes → Proceed with testing
```

## Workflow

1. **Open browser**: `playwright-cli open <url>`
2. **Snapshot elements**: `playwright-cli snapshot` — gets refs (e1, e2, ...)
3. **Interact**: `playwright-cli click e1`, `playwright-cli fill e2 "text"`
4. **Re-snapshot**: verify result after each action
5. **Screenshot**: `playwright-cli screenshot` for visual record
6. **Close**: `playwright-cli close`

## Key Commands

| Action | Command |
|--------|---------|
| Navigate | `playwright-cli open <url>` |
| Get elements | `playwright-cli snapshot` |
| Click | `playwright-cli click e1` |
| Fill input | `playwright-cli fill e1 "value"` |
| Take screenshot | `playwright-cli screenshot` |
| Check console | `playwright-cli console` |
| Close | `playwright-cli close` |

## Critical Rules

- Always `snapshot` before interacting — refs change after each action
- Wait for load: `playwright-cli run-code "async page => { await page.waitForLoadState('networkidle'); }"`
- Test the full user flow, not just individual elements
- Capture screenshots as evidence for each test scenario

## Test Checklist

- [ ] Main user workflow completes without errors
- [ ] Forms validate and show correct error messages
- [ ] Success states display after operations
- [ ] Navigation works between pages
- [ ] No console errors during normal usage
