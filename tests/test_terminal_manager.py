import contextlib
import secrets
from unittest.mock import MagicMock, patch

import pytest


class TestTerminalManager:
    @pytest.mark.asyncio
    async def test_create_session_returns_id(self):
        from stratus.terminal.manager import TerminalManager

        manager = TerminalManager()

        with patch.object(manager, "_create_pty") as mock_create_pty:
            mock_pty = MagicMock()
            mock_pty.pid = 12345
            mock_pty.master_fd = 10
            mock_pty.cols = 80
            mock_pty.rows = 24
            mock_pty.shell = "/bin/bash"
            mock_pty.cwd = "/home/user"
            mock_pty.is_running = True
            mock_create_pty.return_value = mock_pty

            session_id = await manager.create_session(cols=80, rows=24)

            assert session_id is not None
            assert len(session_id) == 16

    @pytest.mark.asyncio
    async def test_create_session_stores_session(self):
        from stratus.terminal.manager import TerminalManager

        manager = TerminalManager()

        with patch.object(manager, "_create_pty") as mock_create_pty:
            mock_pty = MagicMock()
            mock_pty.pid = 12345
            mock_pty.master_fd = 10
            mock_pty.cols = 80
            mock_pty.rows = 24
            mock_pty.shell = "/bin/bash"
            mock_pty.cwd = "/home/user"
            mock_pty.is_running = True
            mock_create_pty.return_value = mock_pty

            session_id = await manager.create_session(cols=80, rows=24)

            assert session_id in manager._sessions

    @pytest.mark.asyncio
    async def test_get_session_returns_pty(self):
        from stratus.terminal.manager import TerminalManager

        manager = TerminalManager()

        with patch.object(manager, "_create_pty") as mock_create_pty:
            mock_pty = MagicMock()
            mock_pty.pid = 12345
            mock_pty.master_fd = 10
            mock_pty.cols = 80
            mock_pty.rows = 24
            mock_pty.shell = "/bin/bash"
            mock_pty.cwd = "/home/user"
            mock_pty.is_running = True
            mock_create_pty.return_value = mock_pty

            session_id = await manager.create_session(cols=80, rows=24)

            session = manager.get_session(session_id)
            assert session is not None
            assert session.pid == 12345

    @pytest.mark.asyncio
    async def test_get_session_nonexistent_returns_none(self):
        from stratus.terminal.manager import TerminalManager

        manager = TerminalManager()

        session = manager.get_session("nonexistent")
        assert session is None

    @pytest.mark.asyncio
    async def test_destroy_session_closes_pty(self):
        from stratus.terminal.manager import TerminalManager

        manager = TerminalManager()

        with patch.object(manager, "_create_pty") as mock_create_pty:
            mock_pty = MagicMock()
            mock_pty.pid = 12345
            mock_pty.master_fd = 10
            mock_pty.cols = 80
            mock_pty.rows = 24
            mock_pty.shell = "/bin/bash"
            mock_pty.cwd = "/home/user"
            mock_pty.is_running = True
            mock_pty.close = MagicMock(return_value=None)
            mock_pty.close.coroutine = None
            mock_create_pty.return_value = mock_pty

            session_id = await manager.create_session(cols=80, rows=24)

            async def mock_close():
                pass

            mock_pty.close = mock_close

            await manager.destroy_session(session_id)

            assert session_id not in manager._sessions

    @pytest.mark.asyncio
    async def test_destroy_nonexistent_safe(self):
        from stratus.terminal.manager import TerminalManager

        manager = TerminalManager()

        await manager.destroy_session("nonexistent")

    @pytest.mark.asyncio
    async def test_cleanup_all_on_shutdown(self):
        from stratus.terminal.manager import TerminalManager

        manager = TerminalManager()

        closed_sessions = []

        async def mock_close():
            closed_sessions.append(1)

        with patch.object(manager, "_create_pty") as mock_create_pty:
            mock_pty = MagicMock()
            mock_pty.pid = 12345
            mock_pty.master_fd = 10
            mock_pty.cols = 80
            mock_pty.rows = 24
            mock_pty.shell = "/bin/bash"
            mock_pty.cwd = "/home/user"
            mock_pty.is_running = True
            mock_pty.close = mock_close
            mock_create_pty.return_value = mock_pty

            await manager.create_session(cols=80, rows=24)
            await manager.create_session(cols=80, rows=24)

            await manager.cleanup_all()

            assert len(closed_sessions) == 2
            assert len(manager._sessions) == 0


class TestTokenValidation:
    def test_generate_token_unique(self):
        from stratus.terminal.manager import TerminalManager

        manager = TerminalManager()

        token1 = manager._generate_token()
        token2 = manager._generate_token()

        assert token1 != token2
        assert len(token1) >= 32

    def test_validate_token_valid(self):
        from stratus.terminal.manager import TerminalManager

        manager = TerminalManager()
        token = manager._generate_token()

        assert manager.validate_token(token) is True

    def test_validate_token_invalid(self):
        from stratus.terminal.manager import TerminalManager

        manager = TerminalManager()

        assert manager.validate_token("invalid_token") is False


class TestMaxSessions:
    @pytest.mark.asyncio
    async def test_max_sessions_limit(self):
        from stratus.terminal.manager import TerminalManager
        from stratus.terminal.config import TerminalConfig

        config = TerminalConfig(max_sessions=2)
        manager = TerminalManager(config=config)

        with patch.object(manager, "_create_pty") as mock_create_pty:
            mock_pty = MagicMock()
            mock_pty.pid = 12345
            mock_pty.master_fd = 10
            mock_pty.cols = 80
            mock_pty.rows = 24
            mock_pty.shell = "/bin/bash"
            mock_pty.cwd = "/home/user"
            mock_pty.is_running = True
            mock_create_pty.return_value = mock_pty

            await manager.create_session(cols=80, rows=24)
            await manager.create_session(cols=80, rows=24)

            with pytest.raises(RuntimeError, match="Maximum sessions"):
                await manager.create_session(cols=80, rows=24)


class TestSessionList:
    @pytest.mark.asyncio
    async def test_list_sessions_empty(self):
        from stratus.terminal.manager import TerminalManager

        manager = TerminalManager()

        sessions = manager.list_sessions()
        assert sessions == []

    @pytest.mark.asyncio
    async def test_list_sessions_with_sessions(self):
        from stratus.terminal.manager import TerminalManager

        manager = TerminalManager()

        with patch.object(manager, "_create_pty") as mock_create_pty:
            mock_pty = MagicMock()
            mock_pty.pid = 12345
            mock_pty.master_fd = 10
            mock_pty.cols = 80
            mock_pty.rows = 24
            mock_pty.shell = "/bin/bash"
            mock_pty.cwd = "/home/user"
            mock_pty.is_running = True
            mock_create_pty.return_value = mock_pty

            session_id = await manager.create_session(cols=80, rows=24)

            sessions = manager.list_sessions()
            assert len(sessions) == 1
            assert sessions[0]["id"] == session_id
            assert sessions[0]["pid"] == 12345
