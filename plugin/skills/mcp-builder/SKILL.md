---
name: mcp-builder
description: Create MCP servers to integrate external APIs and services with Claude Code. Use when building new MCP tools, extending Claude's capabilities, or integrating third-party services.
context: fork
agent: implementation-expert
---

# MCP Server Builder

Build high-quality MCP servers following the 4-phase process.

## Phase 1: Research & Plan

1. **Understand the API** — read docs, identify key endpoints, note auth mechanism
2. **Design tools** — each tool = one atomic operation; name clearly (`service_action_resource`)
3. **Choose transport**:
   - `stdio` for local tools (Claude Code integration)
   - Streamable HTTP for remote/multi-user servers
4. **Choose language**: Python (FastMCP) for local tools, TypeScript for remote

## Phase 2: Implement

### Python (FastMCP) — preferred for local tools

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("my-service")

@mcp.tool()
def get_resource(id: str) -> dict:
    """Get a resource by ID. Returns the full resource object."""
    # implementation
    return client.get(id)

if __name__ == "__main__":
    mcp.run()
```

### Tool Design Rules

- **One tool = one action**: `create_issue`, not `manage_issues`
- **Descriptive names**: `github_create_issue`, not `create`
- **Actionable errors**: "Repository not found. Check the repo name." not "Error 404"
- **Return focused data**: filter large responses, don't dump raw API output
- **Annotate behavior**: `readOnlyHint=True` for read operations

### MCP Config (`.mcp.json`)

```json
{
  "mcpServers": {
    "my-service": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "python", "server.py"]
    }
  }
}
```

## Phase 3: Test

```bash
# Verify syntax
python -m py_compile server.py

# Test with MCP Inspector
npx @modelcontextprotocol/inspector uv run python server.py
```

Check each tool:
- Returns correct data for valid input
- Returns actionable error for invalid input
- Handles pagination for list operations
- Auth errors give clear instructions

## Phase 4: Evaluate

Create 5-10 test questions that require multiple tool calls to answer. Verify each answer independently. Document edge cases.

## Checklist

- [ ] Each tool has a clear, descriptive docstring
- [ ] Auth errors guide the user to fix them
- [ ] Large responses are filtered/paginated
- [ ] `readOnlyHint` set correctly
- [ ] Tested with MCP Inspector
- [ ] `.mcp.json` entry added
