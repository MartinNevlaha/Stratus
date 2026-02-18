---
name: implement-mcp
description: Implements a new MCP tool. Use when the user asks to create a new tool or server.
agent: implementation-expert
context: fork
---

Implement a new MCP tool described as: "$ARGUMENTS"

1.  Look for existing MCP server code in the project to understand patterns.
2.  Create the implementation using the `mcp` Python package or the appropriate SDK.
3.  Ensure it follows the project's established transport pattern (stdio, SSE, etc.).
4.  Add a test case to verify the tool schema and behavior.
