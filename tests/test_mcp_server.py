"""Tests for MCP memory server and HTTP client."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from stratus.mcp_server.client import MemoryClient
from stratus.mcp_server.server import create_mcp_server


class TestMemoryClient:
    def test_memory_client_uses_env_port(self, monkeypatch):
        """MemoryClient respects AI_FRAMEWORK_PORT env var."""
        monkeypatch.setenv("AI_FRAMEWORK_PORT", "9999")
        from unittest.mock import patch

        with patch("stratus.hooks._common.get_api_url", return_value="http://localhost:9999"):
            import importlib

            import stratus.mcp_server.client as client_module

            importlib.reload(client_module)
            client = client_module.MemoryClient()
            assert "9999" in client._base_url
            import asyncio

            asyncio.run(client.close())

    @pytest.mark.asyncio
    async def test_search_builds_correct_url(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [], "count": 0}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        client = MemoryClient(base_url="http://localhost:41777")
        client._client = mock_client

        result = await client.search("test query", limit=10)
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "/api/search" in str(call_args)
        assert result == {"results": [], "count": 0}

    @pytest.mark.asyncio
    async def test_save_memory_posts_json(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 1}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        client = MemoryClient(base_url="http://localhost:41777")
        client._client = mock_client

        result = await client.save_memory(text="test", title="Test")
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/api/memory/save" in str(call_args)
        assert result == {"id": 1}

    @pytest.mark.asyncio
    async def test_timeline_passes_params(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"events": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        client = MemoryClient(base_url="http://localhost:41777")
        client._client = mock_client

        result = await client.timeline(anchor_id=5, depth_before=3, depth_after=3)
        mock_client.get.assert_called_once()
        assert result == {"events": []}

    @pytest.mark.asyncio
    async def test_get_observations_posts_ids(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"events": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        client = MemoryClient(base_url="http://localhost:41777")
        client._client = mock_client

        result = await client.get_observations(ids=[1, 2, 3])
        mock_client.post.assert_called_once()
        assert result == {"events": []}

    @pytest.mark.asyncio
    async def test_health_check(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        client = MemoryClient(base_url="http://localhost:41777")
        client._client = mock_client

        result = await client.health()
        assert result == {"status": "ok"}


class TestMCPServer:
    def test_server_creation(self):
        server = create_mcp_server()
        assert server is not None

    @pytest.mark.asyncio
    async def test_list_tools_returns_seven_tools(self):
        server = create_mcp_server()
        from mcp import types

        result = await server.request_handlers[types.ListToolsRequest](
            types.ListToolsRequest(method="tools/list")
        )
        # ServerResult wraps the actual result via .root
        tools = result.root.tools
        tool_names = {t.name for t in tools}
        assert tool_names == {
            "search",
            "timeline",
            "get_observations",
            "save_memory",
            "retrieve",
            "index_status",
            "delivery_dispatch",
        }

    @pytest.mark.asyncio
    async def test_tool_schemas_have_required_fields(self):
        server = create_mcp_server()
        from mcp import types

        result = await server.request_handlers[types.ListToolsRequest](
            types.ListToolsRequest(method="tools/list")
        )
        for tool in result.root.tools:
            assert tool.name is not None
            assert tool.description is not None
            assert tool.inputSchema is not None

    @pytest.mark.asyncio
    async def test_search_tool_schema(self):
        server = create_mcp_server()
        from mcp import types

        result = await server.request_handlers[types.ListToolsRequest](
            types.ListToolsRequest(method="tools/list")
        )
        search_tool = next(t for t in result.root.tools if t.name == "search")
        props = search_tool.inputSchema["properties"]
        assert "query" in props

    @pytest.mark.asyncio
    async def test_save_memory_tool_schema(self):
        server = create_mcp_server()
        from mcp import types

        result = await server.request_handlers[types.ListToolsRequest](
            types.ListToolsRequest(method="tools/list")
        )
        save_tool = next(t for t in result.root.tools if t.name == "save_memory")
        assert "text" in save_tool.inputSchema.get("required", [])

    @pytest.mark.asyncio
    async def test_call_tool_search(self):
        from unittest.mock import patch

        server = create_mcp_server()
        from mcp import types

        mock_client = AsyncMock()
        mock_client.search = AsyncMock(return_value={"results": [], "count": 0})
        mock_client.close = AsyncMock()

        with patch("stratus.mcp_server.server.MemoryClient", return_value=mock_client):
            result = await server.request_handlers[types.CallToolRequest](
                types.CallToolRequest(
                    method="tools/call",
                    params=types.CallToolRequestParams(name="search", arguments={"query": "test"}),
                )
            )
        content = result.root.content
        assert len(content) == 1
        assert "results" in content[0].text

    @pytest.mark.asyncio
    async def test_call_tool_save_memory(self):
        from unittest.mock import patch

        server = create_mcp_server()
        from mcp import types

        mock_client = AsyncMock()
        mock_client.save_memory = AsyncMock(return_value={"id": 42})
        mock_client.close = AsyncMock()

        with patch("stratus.mcp_server.server.MemoryClient", return_value=mock_client):
            result = await server.request_handlers[types.CallToolRequest](
                types.CallToolRequest(
                    method="tools/call",
                    params=types.CallToolRequestParams(
                        name="save_memory", arguments={"text": "remember this"}
                    ),
                )
            )
        content = result.root.content
        assert '"id": 42' in content[0].text

    @pytest.mark.asyncio
    async def test_call_tool_get_observations(self):
        from unittest.mock import patch

        server = create_mcp_server()
        from mcp import types

        mock_client = AsyncMock()
        mock_client.get_observations = AsyncMock(return_value={"events": []})
        mock_client.close = AsyncMock()

        with patch("stratus.mcp_server.server.MemoryClient", return_value=mock_client):
            result = await server.request_handlers[types.CallToolRequest](
                types.CallToolRequest(
                    method="tools/call",
                    params=types.CallToolRequestParams(
                        name="get_observations", arguments={"ids": [1, 2]}
                    ),
                )
            )
        content = result.root.content
        assert "events" in content[0].text

    @pytest.mark.asyncio
    async def test_call_tool_timeline(self):
        from unittest.mock import patch

        server = create_mcp_server()
        from mcp import types

        mock_client = AsyncMock()
        mock_client.timeline = AsyncMock(return_value={"events": []})
        mock_client.close = AsyncMock()

        with patch("stratus.mcp_server.server.MemoryClient", return_value=mock_client):
            result = await server.request_handlers[types.CallToolRequest](
                types.CallToolRequest(
                    method="tools/call",
                    params=types.CallToolRequestParams(name="timeline", arguments={"anchor_id": 5}),
                )
            )
        content = result.root.content
        assert "events" in content[0].text

    @pytest.mark.asyncio
    async def test_call_tool_unknown(self):
        from unittest.mock import patch

        server = create_mcp_server()
        from mcp import types

        mock_client = AsyncMock()
        mock_client.close = AsyncMock()

        with patch("stratus.mcp_server.server.MemoryClient", return_value=mock_client):
            result = await server.request_handlers[types.CallToolRequest](
                types.CallToolRequest(
                    method="tools/call",
                    params=types.CallToolRequestParams(name="nonexistent", arguments={}),
                )
            )
        content = result.root.content
        assert "Unknown tool" in content[0].text

    @pytest.mark.asyncio
    async def test_list_tools_returns_all_tools(self):
        server = create_mcp_server()
        from mcp import types

        result = await server.request_handlers[types.ListToolsRequest](
            types.ListToolsRequest(method="tools/list")
        )
        tools = result.root.tools
        tool_names = {t.name for t in tools}
        assert tool_names == {
            "search",
            "timeline",
            "get_observations",
            "save_memory",
            "retrieve",
            "index_status",
            "delivery_dispatch",
        }

    @pytest.mark.asyncio
    async def test_retrieve_tool_schema(self):
        server = create_mcp_server()
        from mcp import types

        result = await server.request_handlers[types.ListToolsRequest](
            types.ListToolsRequest(method="tools/list")
        )
        retrieve_tool = next(t for t in result.root.tools if t.name == "retrieve")
        props = retrieve_tool.inputSchema["properties"]
        assert "query" in props
        assert "corpus" in props
        assert "top_k" in props
        assert "query" in retrieve_tool.inputSchema.get("required", [])

    @pytest.mark.asyncio
    async def test_call_tool_retrieve(self):
        from unittest.mock import MagicMock, patch

        server = create_mcp_server()
        from mcp import types

        mock_response = MagicMock()
        mock_response.model_dump.return_value = {
            "results": [],
            "corpus": "code",
            "query_time_ms": 5.0,
        }
        mock_retriever = MagicMock()
        mock_retriever.retrieve = MagicMock(return_value=mock_response)
        mock_retriever_cls = MagicMock(return_value=mock_retriever)

        mock_client = AsyncMock()
        mock_client.close = AsyncMock()

        with (
            patch("stratus.mcp_server.server.MemoryClient", return_value=mock_client),
            patch(
                "stratus.retrieval.unified.UnifiedRetriever",
                mock_retriever_cls,
            ),
        ):
            result = await server.request_handlers[types.CallToolRequest](
                types.CallToolRequest(
                    method="tools/call",
                    params=types.CallToolRequestParams(
                        name="retrieve",
                        arguments={"query": "where is retry logic", "top_k": 5},
                    ),
                )
            )
        content = result.root.content
        assert len(content) == 1
        assert "corpus" in content[0].text

    @pytest.mark.asyncio
    async def test_delivery_dispatch_tool_listed(self):
        server = create_mcp_server()
        from mcp import types

        result = await server.request_handlers[types.ListToolsRequest](
            types.ListToolsRequest(method="tools/list")
        )
        tool_names = {t.name for t in result.root.tools}
        assert "delivery_dispatch" in tool_names

    @pytest.mark.asyncio
    async def test_call_tool_delivery_dispatch(self):
        from unittest.mock import MagicMock, patch

        import httpx

        server = create_mcp_server()
        from mcp import types

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "phase": "implementation",
            "agents": [],
            "objectives": [],
            "briefing_markdown": "# Phase",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.close = AsyncMock()

        with (
            patch("stratus.mcp_server.server.MemoryClient", return_value=mock_client),
            patch("httpx.get", return_value=mock_response),
        ):
            result = await server.request_handlers[types.CallToolRequest](
                types.CallToolRequest(
                    method="tools/call",
                    params=types.CallToolRequestParams(
                        name="delivery_dispatch",
                        arguments={},
                    ),
                )
            )
        content = result.root.content
        assert len(content) == 1
        assert "phase" in content[0].text

    @pytest.mark.asyncio
    async def test_call_tool_index_status(self):
        from unittest.mock import MagicMock, patch

        server = create_mcp_server()
        from mcp import types

        mock_retriever = MagicMock()
        mock_retriever.status = MagicMock(
            return_value={"vexor_available": True, "governance_available": False}
        )
        mock_retriever_cls = MagicMock(return_value=mock_retriever)

        mock_client = AsyncMock()
        mock_client.close = AsyncMock()

        with (
            patch("stratus.mcp_server.server.MemoryClient", return_value=mock_client),
            patch(
                "stratus.retrieval.unified.UnifiedRetriever",
                mock_retriever_cls,
            ),
        ):
            result = await server.request_handlers[types.CallToolRequest](
                types.CallToolRequest(
                    method="tools/call",
                    params=types.CallToolRequestParams(
                        name="index_status",
                        arguments={},
                    ),
                )
            )
        content = result.root.content
        assert len(content) == 1
        assert "vexor_available" in content[0].text

    @pytest.mark.asyncio
    async def test_retrieve_creates_governance_store_and_passes_directly(self):
        """retrieve handler must construct GovernanceStore and pass it directly."""
        from unittest.mock import MagicMock, patch

        server = create_mcp_server()
        from mcp import types

        mock_gov_store = MagicMock()
        mock_gov_store_cls = MagicMock(return_value=mock_gov_store)

        mock_response = MagicMock()
        mock_response.model_dump.return_value = {
            "results": [],
            "corpus": "governance",
            "query_time_ms": 1.0,
        }
        mock_retriever = MagicMock()
        mock_retriever.retrieve = MagicMock(return_value=mock_response)
        mock_retriever_cls = MagicMock(return_value=mock_retriever)

        mock_client = AsyncMock()
        mock_client.close = AsyncMock()

        with (
            patch("stratus.mcp_server.server.MemoryClient", return_value=mock_client),
            patch("stratus.retrieval.governance_store.GovernanceStore", mock_gov_store_cls),
            patch("stratus.retrieval.unified.UnifiedRetriever", mock_retriever_cls),
        ):
            result = await server.request_handlers[types.CallToolRequest](
                types.CallToolRequest(
                    method="tools/call",
                    params=types.CallToolRequestParams(
                        name="retrieve",
                        arguments={"query": "error handling pattern"},
                    ),
                )
            )

        # GovernanceStore must have been constructed
        mock_gov_store_cls.assert_called_once()
        # UnifiedRetriever must have received governance=gov_store
        _, retriever_kwargs = mock_retriever_cls.call_args
        assert retriever_kwargs.get("governance") is mock_gov_store
        # GovernanceStore.close() must be called after retrieval
        mock_gov_store.close.assert_called_once()

        content = result.root.content
        assert len(content) == 1
        assert "corpus" in content[0].text

    @pytest.mark.asyncio
    async def test_index_status_creates_governance_store_and_passes_directly(self):
        """index_status handler must construct GovernanceStore and pass it directly."""
        from unittest.mock import MagicMock, patch

        server = create_mcp_server()
        from mcp import types

        mock_gov_store = MagicMock()
        mock_gov_store_cls = MagicMock(return_value=mock_gov_store)

        mock_retriever = MagicMock()
        mock_retriever.status = MagicMock(
            return_value={"vexor_available": False, "governance_available": True}
        )
        mock_retriever_cls = MagicMock(return_value=mock_retriever)

        mock_client = AsyncMock()
        mock_client.close = AsyncMock()

        with (
            patch("stratus.mcp_server.server.MemoryClient", return_value=mock_client),
            patch("stratus.retrieval.governance_store.GovernanceStore", mock_gov_store_cls),
            patch("stratus.retrieval.unified.UnifiedRetriever", mock_retriever_cls),
        ):
            result = await server.request_handlers[types.CallToolRequest](
                types.CallToolRequest(
                    method="tools/call",
                    params=types.CallToolRequestParams(
                        name="index_status",
                        arguments={},
                    ),
                )
            )

        # GovernanceStore must have been constructed
        mock_gov_store_cls.assert_called_once()
        # UnifiedRetriever must have received governance=gov_store
        _, retriever_kwargs = mock_retriever_cls.call_args
        assert retriever_kwargs.get("governance") is mock_gov_store
        # GovernanceStore.close() must be called after status check
        mock_gov_store.close.assert_called_once()

        content = result.root.content
        assert len(content) == 1
        assert "governance_available" in content[0].text

    @pytest.mark.asyncio
    async def test_retrieve_indexes_governance_when_project_root_known(self):
        """retrieve handler must call governance.index_project(project_root) before retrieval."""
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        server = create_mcp_server()
        from mcp import types

        mock_gov_store = MagicMock()
        mock_gov_store_cls = MagicMock(return_value=mock_gov_store)

        mock_response = MagicMock()
        mock_response.model_dump.return_value = {
            "results": [],
            "corpus": "governance",
            "query_time_ms": 1.0,
        }
        mock_retriever = MagicMock()
        mock_retriever.retrieve = MagicMock(return_value=mock_response)
        mock_retriever_cls = MagicMock(return_value=mock_retriever)

        mock_client = AsyncMock()
        mock_client.close = AsyncMock()

        fake_git_root = Path("/tmp/fake-project")

        with (
            patch("stratus.mcp_server.server.MemoryClient", return_value=mock_client),
            patch("stratus.retrieval.governance_store.GovernanceStore", mock_gov_store_cls),
            patch("stratus.retrieval.unified.UnifiedRetriever", mock_retriever_cls),
            patch(
                "stratus.hooks._common.get_git_root",
                return_value=fake_git_root,
            ),
        ):
            await server.request_handlers[types.CallToolRequest](
                types.CallToolRequest(
                    method="tools/call",
                    params=types.CallToolRequestParams(
                        name="retrieve",
                        arguments={"query": "error handling pattern"},
                    ),
                )
            )

        # governance.index_project() must have been called with the resolved project root
        mock_gov_store.index_project.assert_called_once_with(str(fake_git_root.resolve()))

    @pytest.mark.asyncio
    async def test_retrieve_skips_governance_index_when_no_git_root(self):
        """retrieve handler must NOT call governance.index_project() when project root is None."""
        from unittest.mock import MagicMock, patch

        server = create_mcp_server()
        from mcp import types

        mock_gov_store = MagicMock()
        mock_gov_store_cls = MagicMock(return_value=mock_gov_store)

        mock_response = MagicMock()
        mock_response.model_dump.return_value = {
            "results": [],
            "corpus": "governance",
            "query_time_ms": 1.0,
        }
        mock_retriever = MagicMock()
        mock_retriever.retrieve = MagicMock(return_value=mock_response)
        mock_retriever_cls = MagicMock(return_value=mock_retriever)

        mock_client = AsyncMock()
        mock_client.close = AsyncMock()

        with (
            patch("stratus.mcp_server.server.MemoryClient", return_value=mock_client),
            patch("stratus.retrieval.governance_store.GovernanceStore", mock_gov_store_cls),
            patch("stratus.retrieval.unified.UnifiedRetriever", mock_retriever_cls),
            patch("stratus.hooks._common.get_git_root", return_value=None),
        ):
            await server.request_handlers[types.CallToolRequest](
                types.CallToolRequest(
                    method="tools/call",
                    params=types.CallToolRequestParams(
                        name="retrieve",
                        arguments={"query": "error handling pattern"},
                    ),
                )
            )

        # governance.index_project() must NOT have been called when git root is None
        mock_gov_store.index_project.assert_not_called()

    @pytest.mark.asyncio
    async def test_index_status_indexes_governance_when_project_root_known(self):
        """index_status handler must call governance.index_project() before status check."""
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        server = create_mcp_server()
        from mcp import types

        mock_gov_store = MagicMock()
        mock_gov_store_cls = MagicMock(return_value=mock_gov_store)

        mock_retriever = MagicMock()
        mock_retriever.status = MagicMock(
            return_value={"vexor_available": False, "governance_available": True}
        )
        mock_retriever_cls = MagicMock(return_value=mock_retriever)

        mock_client = AsyncMock()
        mock_client.close = AsyncMock()

        fake_git_root = Path("/tmp/fake-project")

        with (
            patch("stratus.mcp_server.server.MemoryClient", return_value=mock_client),
            patch("stratus.retrieval.governance_store.GovernanceStore", mock_gov_store_cls),
            patch("stratus.retrieval.unified.UnifiedRetriever", mock_retriever_cls),
            patch(
                "stratus.hooks._common.get_git_root",
                return_value=fake_git_root,
            ),
        ):
            await server.request_handlers[types.CallToolRequest](
                types.CallToolRequest(
                    method="tools/call",
                    params=types.CallToolRequestParams(
                        name="index_status",
                        arguments={},
                    ),
                )
            )

        # governance.index_project() must have been called with the resolved project root
        mock_gov_store.index_project.assert_called_once_with(str(fake_git_root.resolve()))

    @pytest.mark.asyncio
    async def test_index_status_skips_governance_index_when_no_git_root(self):
        """index_status handler must NOT call governance.index_project() when root is None."""
        from unittest.mock import MagicMock, patch

        server = create_mcp_server()
        from mcp import types

        mock_gov_store = MagicMock()
        mock_gov_store_cls = MagicMock(return_value=mock_gov_store)

        mock_retriever = MagicMock()
        mock_retriever.status = MagicMock(
            return_value={"vexor_available": False, "governance_available": True}
        )
        mock_retriever_cls = MagicMock(return_value=mock_retriever)

        mock_client = AsyncMock()
        mock_client.close = AsyncMock()

        with (
            patch("stratus.mcp_server.server.MemoryClient", return_value=mock_client),
            patch("stratus.retrieval.governance_store.GovernanceStore", mock_gov_store_cls),
            patch("stratus.retrieval.unified.UnifiedRetriever", mock_retriever_cls),
            patch("stratus.hooks._common.get_git_root", return_value=None),
        ):
            await server.request_handlers[types.CallToolRequest](
                types.CallToolRequest(
                    method="tools/call",
                    params=types.CallToolRequestParams(
                        name="index_status",
                        arguments={},
                    ),
                )
            )

        # governance.index_project() must NOT have been called when git root is None
        mock_gov_store.index_project.assert_not_called()
