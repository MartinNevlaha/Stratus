import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient


def make_mock_pty():
    mock_pty = MagicMock()
    mock_pty.pid = 12345
    mock_pty.master_fd = 10
    mock_pty.cols = 80
    mock_pty.rows = 24
    mock_pty.shell = "/bin/bash"
    mock_pty.cwd = "/home/user"
    mock_pty.is_running = True
    mock_pty.active = True
    mock_pty.read_output = asyncio.Queue()
    mock_pty.close = AsyncMock()
    mock_pty.write = AsyncMock()
    mock_pty.resize = AsyncMock()
    return mock_pty


@pytest.fixture
def client():
    from stratus.server.app import create_app

    app = create_app(db_path=":memory:", learning_db_path=":memory:")

    from stratus.terminal.manager import TerminalManager

    manager = TerminalManager()
    app.state.terminal_manager = manager

    with TestClient(app) as c:
        yield c


class TestTerminalWebSocket:
    @pytest.mark.asyncio
    async def test_connect_accepts(self, client: TestClient):
        with client.websocket_connect("/api/terminal/ws") as websocket:
            pass

    @pytest.mark.asyncio
    async def test_create_message_creates_session(self, client: TestClient):
        manager = client.app.state.terminal_manager

        with patch.object(manager, "_create_pty") as mock_create_pty:
            mock_pty = make_mock_pty()
            mock_create_pty.return_value = mock_pty

            with client.websocket_connect("/api/terminal/ws") as websocket:
                websocket.send_json({"type": "create", "cols": 80, "rows": 24})
                response = websocket.receive_json()

                assert response["type"] == "created"
                assert "session_id" in response

    @pytest.mark.asyncio
    async def test_input_forwards_to_pty(self, client: TestClient):
        manager = client.app.state.terminal_manager

        with patch.object(manager, "_create_pty") as mock_create_pty:
            mock_pty = make_mock_pty()
            mock_create_pty.return_value = mock_pty

            with client.websocket_connect("/api/terminal/ws") as websocket:
                websocket.send_json({"type": "create", "cols": 80, "rows": 24})
                response = websocket.receive_json()

                session_id = response["session_id"]
                websocket.send_json({"type": "input", "session_id": session_id, "data": "ls\n"})

                await asyncio.sleep(0.1)
                mock_pty.write.assert_called()

    @pytest.mark.asyncio
    async def test_resize_updates_pty(self, client: TestClient):
        manager = client.app.state.terminal_manager

        with patch.object(manager, "_create_pty") as mock_create_pty:
            mock_pty = make_mock_pty()
            mock_create_pty.return_value = mock_pty

            with client.websocket_connect("/api/terminal/ws") as websocket:
                websocket.send_json({"type": "create", "cols": 80, "rows": 24})
                response = websocket.receive_json()

                session_id = response["session_id"]
                websocket.send_json(
                    {"type": "resize", "session_id": session_id, "cols": 120, "rows": 40}
                )

                await asyncio.sleep(0.1)
                mock_pty.resize.assert_called()

    @pytest.mark.asyncio
    async def test_disconnect_cleans_up_session(self, client: TestClient):
        manager = client.app.state.terminal_manager

        with patch.object(manager, "_create_pty") as mock_create_pty:
            mock_pty = make_mock_pty()
            mock_create_pty.return_value = mock_pty

            with client.websocket_connect("/api/terminal/ws") as websocket:
                websocket.send_json({"type": "create", "cols": 80, "rows": 24})
                response = websocket.receive_json()
                session_id = response["session_id"]

            await asyncio.sleep(0.1)
            assert session_id not in manager._sessions

    @pytest.mark.asyncio
    async def test_invalid_message_returns_error(self, client: TestClient):
        with client.websocket_connect("/api/terminal/ws") as websocket:
            websocket.send_json({"type": "invalid_type"})
            response = websocket.receive_json()

            assert response["type"] == "error"

    @pytest.mark.asyncio
    async def test_heartbeat_ping_pong(self, client: TestClient):
        with client.websocket_connect("/api/terminal/ws") as websocket:
            websocket.send_json({"type": "ping"})
            response = websocket.receive_json()

            assert response["type"] == "pong"

    @pytest.mark.asyncio
    async def test_input_without_session_returns_error(self, client: TestClient):
        with client.websocket_connect("/api/terminal/ws") as websocket:
            websocket.send_json({"type": "input", "session_id": "nonexistent", "data": "test"})
            response = websocket.receive_json()

            assert response["type"] == "error"


class TestTerminalHTTPRoutes:
    def test_status_endpoint(self, client: TestClient):
        resp = client.get("/api/terminal/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "enabled" in data

    def test_sessions_list_empty(self, client: TestClient):
        resp = client.get("/api/terminal/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sessions"] == []
        assert data["count"] == 0

    def test_sessions_list_with_sessions(self, client: TestClient):
        manager = client.app.state.terminal_manager

        with patch.object(manager, "_create_pty") as mock_create_pty:
            mock_pty = make_mock_pty()
            mock_create_pty.return_value = mock_pty

            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            session_id = loop.run_until_complete(manager.create_session(cols=80, rows=24))
            loop.close()

            resp = client.get("/api/terminal/sessions")
            assert resp.status_code == 200
            data = resp.json()
            assert data["count"] == 1
            assert len(data["sessions"]) == 1
            assert data["sessions"][0]["id"] == session_id
