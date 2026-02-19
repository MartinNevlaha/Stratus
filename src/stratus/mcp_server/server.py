"""MCP stdio server with 6 tool handlers proxying to the memory HTTP API."""

from __future__ import annotations

import json

import anyio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server

from stratus.mcp_server.client import MemoryClient

SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Full-text search query"},
        "limit": {"type": "integer", "description": "Max results (default: 20)", "default": 20},
        "type": {
            "type": "string",
            "description": "Filter by type",
            "enum": [
                "bugfix",
                "feature",
                "refactor",
                "discovery",
                "decision",
                "change",
                "pattern_candidate",
                "skill_suggestion",
                "rule_proposal",
                "learning_decision",
                "rejected_pattern",
            ],
        },
        "scope": {"type": "string", "enum": ["repo", "global", "user"]},
        "project": {"type": "string", "description": "Filter by project name"},
        "dateStart": {"type": "string", "description": "ISO 8601 start date"},
        "dateEnd": {"type": "string", "description": "ISO 8601 end date"},
        "offset": {"type": "integer", "description": "Pagination offset", "default": 0},
    },
    "required": ["query"],
}

TIMELINE_SCHEMA = {
    "type": "object",
    "properties": {
        "anchor_id": {"type": "integer", "description": "Memory event ID to center on"},
        "query": {"type": "string", "description": "Find best match, then show timeline"},
        "depth_before": {"type": "integer", "default": 10},
        "depth_after": {"type": "integer", "default": 10},
        "project": {"type": "string"},
    },
}

GET_OBSERVATIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "ids": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "Array of memory event IDs to fetch",
        },
        "limit": {"type": "integer"},
        "project": {"type": "string"},
    },
    "required": ["ids"],
}

RETRIEVE_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Search query for code or governance docs"},
        "corpus": {
            "type": "string",
            "enum": ["code", "governance"],
            "description": "Force search corpus. Omit for auto-routing.",
        },
        "top_k": {"type": "integer", "description": "Max results (default: 10)", "default": 10},
    },
    "required": ["query"],
}

INDEX_STATUS_SCHEMA = {
    "type": "object",
    "properties": {},
}

DELIVERY_DISPATCH_SCHEMA = {
    "type": "object",
    "properties": {},
}

SAVE_MEMORY_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string", "description": "Content to remember"},
        "title": {"type": "string", "description": "Short title"},
        "type": {
            "type": "string",
            "enum": [
                "bugfix",
                "feature",
                "refactor",
                "discovery",
                "decision",
                "change",
                "pattern_candidate",
                "skill_suggestion",
                "rule_proposal",
                "learning_decision",
                "rejected_pattern",
            ],
            "default": "discovery",
        },
        "tags": {"type": "array", "items": {"type": "string"}},
        "actor": {"type": "string", "enum": ["user", "agent", "hook", "system"]},
        "scope": {"type": "string", "enum": ["repo", "global", "user"]},
        "importance": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.5},
        "refs": {"type": "object"},
        "ttl": {"type": "string", "description": "ISO 8601 expiration"},
        "dedupe_key": {"type": "string"},
        "project": {"type": "string"},
    },
    "required": ["text"],
}


def create_mcp_server() -> Server:
    """Create and configure the MCP server with 6 tool handlers."""
    server = Server("stratus-memory", "0.1.0")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="search",
                description="Search memory. Returns index with IDs (~50-100 tokens/result).",
                inputSchema=SEARCH_SCHEMA,
            ),
            types.Tool(
                name="timeline",
                description="Get chronological context around a result.",
                inputSchema=TIMELINE_SCHEMA,
            ),
            types.Tool(
                name="get_observations",
                description="Fetch full details for memory event IDs. ALWAYS batch for 2+ items.",
                inputSchema=GET_OBSERVATIONS_SCHEMA,
            ),
            types.Tool(
                name="save_memory",
                description=(
                    "Save a memory for future search. "
                    "Use for important discoveries, decisions, patterns."
                ),
                inputSchema=SAVE_MEMORY_SCHEMA,
            ),
            types.Tool(
                name="retrieve",
                description=(
                    "Semantic search across code (Vexor) and governance docs (DevRag). "
                    "Auto-routes by query type."
                ),
                inputSchema=RETRIEVE_SCHEMA,
            ),
            types.Tool(
                name="index_status",
                description="Check index freshness and backend availability.",
                inputSchema=INDEX_STATUS_SCHEMA,
            ),
            types.Tool(
                name="delivery_dispatch",
                description=(
                    "Get delivery phase briefing, active agents," + " and delegation instructions."
                ),
                inputSchema=DELIVERY_DISPATCH_SCHEMA,
            ),
        ]

    @server.call_tool()
    async def call_tool(
        name: str,
        arguments: dict | None,
    ) -> list[types.TextContent]:
        args = arguments or {}
        client = MemoryClient()
        try:
            if name == "search":
                result = await client.search(
                    query=args["query"],
                    limit=args.get("limit", 20),
                    type=args.get("type"),
                    scope=args.get("scope"),
                    project=args.get("project"),
                    date_start=args.get("dateStart"),
                    date_end=args.get("dateEnd"),
                    offset=args.get("offset", 0),
                )
            elif name == "timeline":
                result = await client.timeline(
                    anchor_id=args.get("anchor_id"),
                    query=args.get("query"),
                    depth_before=args.get("depth_before", 10),
                    depth_after=args.get("depth_after", 10),
                    project=args.get("project"),
                )
            elif name == "get_observations":
                result = await client.get_observations(ids=args["ids"])
            elif name == "save_memory":
                result = await client.save_memory(**args)
            elif name == "retrieve":
                from stratus.hooks._common import get_git_root
                from stratus.retrieval.config import load_retrieval_config
                from stratus.retrieval.unified import UnifiedRetriever

                git_root = get_git_root()
                ai_path = (git_root / ".ai-framework.json") if git_root else None
                config = load_retrieval_config(ai_path)
                retriever = UnifiedRetriever(config=config)
                resp = retriever.retrieve(
                    args["query"],
                    corpus=args.get("corpus"),
                    top_k=args.get("top_k", 10),
                )
                result = resp.model_dump()
            elif name == "index_status":
                from stratus.hooks._common import get_git_root
                from stratus.retrieval.config import load_retrieval_config
                from stratus.retrieval.unified import UnifiedRetriever

                git_root = get_git_root()
                ai_path = (git_root / ".ai-framework.json") if git_root else None
                config = load_retrieval_config(ai_path)
                retriever = UnifiedRetriever(config=config)
                result = retriever.status()
            elif name == "delivery_dispatch":
                import httpx as _httpx

                from stratus.hooks._common import get_api_url

                api_url = get_api_url()
                resp = _httpx.get(
                    f"{api_url}/api/delivery/dispatch",
                    timeout=5.0,
                )
                result = resp.json()
            else:
                return [types.TextContent(type="text", text=f"Unknown tool: {name}")]
        finally:
            await client.close()

        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    return server


async def run_mcp_server() -> None:
    """Run the MCP server with stdio transport."""
    server = create_mcp_server()
    async with stdio_server() as (read_stream, write_stream):
        init_options = server.create_initialization_options(
            notification_options=NotificationOptions(),
        )
        await server.run(read_stream, write_stream, init_options)


def main() -> None:
    anyio.run(run_mcp_server)
