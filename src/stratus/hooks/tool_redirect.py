"""PreToolUse hook: redirect web searches to project-specific tools.

Phase 3 stub — when DevRag/Vexor are available, this will redirect to those
tools instead of just suggesting alternatives.
"""

from __future__ import annotations

import sys

CODE_SEARCH_PATTERNS: list[str] = [
    "implementation",
    "function",
    "class",
    "method",
    "where is",
    "how does",
    "codebase",
]

RULE_SEARCH_PATTERNS: list[str] = [
    "rule",
    "standard",
    "convention",
    "policy",
]

LIBRARY_PATTERNS: list[str] = [
    "mcp",
    "starlette",
    "pydantic",
    "httpx",
    "uvicorn",
    "anyio",
]

WEB_TOOL_NAMES: frozenset[str] = frozenset({"WebSearch", "WebFetch"})


def classify_query(query: str) -> str:
    """Classify a search query as 'code', 'rule', 'library', or 'general'."""
    lower = query.lower()

    if any(pattern in lower for pattern in CODE_SEARCH_PATTERNS):
        return "code"

    if any(pattern in lower for pattern in RULE_SEARCH_PATTERNS):
        return "rule"

    if any(pattern in lower for pattern in LIBRARY_PATTERNS):
        return "library"

    return "general"


def build_redirect_message(classification: str, query: str) -> str | None:
    """Return a redirect suggestion message, or None if no redirect is needed."""
    if classification == "code":
        return (
            f"Tip: For codebase searches, use the 'retrieve' tool for semantic search.\n"
            f"Query: '{query}'\n"
            f"The retrieve tool auto-routes to Vexor for code search."
        )

    if classification == "rule":
        return (
            f"Tip: For rule/convention queries, use the 'retrieve' tool.\n"
            f"Query: '{query}'\n"
            f"The retrieve tool auto-routes to DevRag for governance docs."
        )

    return None


def main() -> None:
    """Entry point for PreToolUse hook."""
    from stratus.hooks._common import read_hook_input

    hook_input = read_hook_input()

    tool_name = hook_input.get("tool_name", "")
    if tool_name not in WEB_TOOL_NAMES:
        sys.exit(0)

    tool_input = hook_input.get("tool_input", {})
    if tool_name == "WebSearch":
        query = tool_input.get("query", "")
    else:
        query = tool_input.get("url", "")

    if not query:
        sys.exit(0)

    classification = classify_query(query)
    message = build_redirect_message(classification, query)

    if message:
        print(message, file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
