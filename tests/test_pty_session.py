import asyncio
import contextlib
import os
import signal
from unittest.mock import MagicMock, patch

import pytest


class TestPTYSessionLifecycle:
    @pytest.mark.asyncio
    async def test_start_forks_process(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch("stratus.terminal.pty_session.pty.fork", return_value=(12345, 10))
            )
            stack.enter_context(patch("stratus.terminal.pty_session.os.set_blocking"))
            stack.enter_context(
                patch("stratus.terminal.pty_session.termios.tcgetattr", return_value=[0] * 7)
            )
            stack.enter_context(patch("stratus.terminal.pty_session.termios.tcsetattr"))
            stack.enter_context(patch("stratus.terminal.pty_session.fcntl.ioctl"))

            mock_loop = MagicMock()
            stack.enter_context(patch("asyncio.get_running_loop", return_value=mock_loop))

            from stratus.terminal.pty_session import PTYSession, pty

            session = PTYSession(cols=80, rows=24)
            await session.start()

            pty.fork.assert_called_once()
            assert session.pid == 12345
            assert session.master_fd == 10

    @pytest.mark.asyncio
    async def test_start_sets_nonblocking(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch("stratus.terminal.pty_session.pty.fork", return_value=(12345, 10))
            )
            mock_set_blocking = stack.enter_context(
                patch("stratus.terminal.pty_session.os.set_blocking")
            )
            stack.enter_context(
                patch("stratus.terminal.pty_session.termios.tcgetattr", return_value=[0] * 7)
            )
            stack.enter_context(patch("stratus.terminal.pty_session.termios.tcsetattr"))
            stack.enter_context(patch("stratus.terminal.pty_session.fcntl.ioctl"))

            mock_loop = MagicMock()
            stack.enter_context(patch("asyncio.get_running_loop", return_value=mock_loop))

            from stratus.terminal.pty_session import PTYSession

            session = PTYSession(cols=80, rows=24)
            await session.start()

            mock_set_blocking.assert_called_once_with(10, False)

    @pytest.mark.asyncio
    async def test_start_sets_window_size(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch("stratus.terminal.pty_session.pty.fork", return_value=(12345, 10))
            )
            stack.enter_context(patch("stratus.terminal.pty_session.os.set_blocking"))
            stack.enter_context(
                patch("stratus.terminal.pty_session.termios.tcgetattr", return_value=[0] * 7)
            )
            stack.enter_context(patch("stratus.terminal.pty_session.termios.tcsetattr"))
            mock_ioctl = stack.enter_context(patch("stratus.terminal.pty_session.fcntl.ioctl"))

            mock_loop = MagicMock()
            stack.enter_context(patch("asyncio.get_running_loop", return_value=mock_loop))

            from stratus.terminal.pty_session import PTYSession

            session = PTYSession(cols=120, rows=40)
            await session.start()

            mock_ioctl.assert_called()

    @pytest.mark.asyncio
    async def test_start_uses_custom_shell(self):
        with contextlib.ExitStack() as stack:
            mock_fork = stack.enter_context(
                patch("stratus.terminal.pty_session.pty.fork", return_value=(12345, 10))
            )
            stack.enter_context(patch("stratus.terminal.pty_session.os.set_blocking"))
            stack.enter_context(
                patch("stratus.terminal.pty_session.termios.tcgetattr", return_value=[0] * 7)
            )
            stack.enter_context(patch("stratus.terminal.pty_session.termios.tcsetattr"))
            stack.enter_context(patch("stratus.terminal.pty_session.fcntl.ioctl"))

            mock_loop = MagicMock()
            stack.enter_context(patch("asyncio.get_running_loop", return_value=mock_loop))

            from stratus.terminal.pty_session import PTYSession

            session = PTYSession(cols=80, rows=24, shell="/bin/zsh")
            assert session.shell == "/bin/zsh"
            await session.start()

            mock_fork.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_uses_custom_cwd(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch("stratus.terminal.pty_session.pty.fork", return_value=(12345, 10))
            )
            stack.enter_context(patch("stratus.terminal.pty_session.os.set_blocking"))
            stack.enter_context(
                patch("stratus.terminal.pty_session.termios.tcgetattr", return_value=[0] * 7)
            )
            stack.enter_context(patch("stratus.terminal.pty_session.termios.tcsetattr"))
            stack.enter_context(patch("stratus.terminal.pty_session.fcntl.ioctl"))

            mock_loop = MagicMock()
            stack.enter_context(patch("asyncio.get_running_loop", return_value=mock_loop))

            from stratus.terminal.pty_session import PTYSession

            session = PTYSession(cols=80, rows=24, cwd="/custom/path")
            await session.start()

            assert session.cwd == "/custom/path"

    @pytest.mark.asyncio
    async def test_write_sends_to_pty(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch("stratus.terminal.pty_session.pty.fork", return_value=(12345, 10))
            )
            stack.enter_context(patch("stratus.terminal.pty_session.os.set_blocking"))
            mock_write = stack.enter_context(patch("stratus.terminal.pty_session.os.write"))
            stack.enter_context(
                patch("stratus.terminal.pty_session.termios.tcgetattr", return_value=[0] * 7)
            )
            stack.enter_context(patch("stratus.terminal.pty_session.termios.tcsetattr"))
            stack.enter_context(patch("stratus.terminal.pty_session.fcntl.ioctl"))

            mock_loop = MagicMock()
            stack.enter_context(patch("asyncio.get_running_loop", return_value=mock_loop))

            from stratus.terminal.pty_session import PTYSession

            session = PTYSession(cols=80, rows=24)
            await session.start()

            await session.write(b"ls -la\n")

            mock_write.assert_called()

    @pytest.mark.asyncio
    async def test_write_raises_when_not_started(self):
        from stratus.terminal.pty_session import PTYSession

        session = PTYSession(cols=80, rows=24)

        with pytest.raises(RuntimeError, match="PTY not started"):
            await session.write(b"test\n")

    @pytest.mark.asyncio
    async def test_resize_updates_winsize(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch("stratus.terminal.pty_session.pty.fork", return_value=(12345, 10))
            )
            stack.enter_context(patch("stratus.terminal.pty_session.os.set_blocking"))
            stack.enter_context(
                patch("stratus.terminal.pty_session.termios.tcgetattr", return_value=[0] * 7)
            )
            stack.enter_context(patch("stratus.terminal.pty_session.termios.tcsetattr"))
            mock_ioctl = stack.enter_context(patch("stratus.terminal.pty_session.fcntl.ioctl"))

            mock_loop = MagicMock()
            stack.enter_context(patch("asyncio.get_running_loop", return_value=mock_loop))

            from stratus.terminal.pty_session import PTYSession

            session = PTYSession(cols=80, rows=24)
            await session.start()

            mock_ioctl.reset_mock()
            await session.resize(120, 40)

            assert session.cols == 120
            assert session.rows == 40
            mock_ioctl.assert_called()

    @pytest.mark.asyncio
    async def test_resize_raises_when_not_started(self):
        from stratus.terminal.pty_session import PTYSession

        session = PTYSession(cols=80, rows=24)

        with pytest.raises(RuntimeError, match="PTY not started"):
            await session.resize(120, 40)

    @pytest.mark.asyncio
    async def test_close_kills_process(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch("stratus.terminal.pty_session.pty.fork", return_value=(12345, 10))
            )
            stack.enter_context(patch("stratus.terminal.pty_session.os.set_blocking"))
            mock_kill = stack.enter_context(patch("stratus.terminal.pty_session.os.kill"))
            mock_close = stack.enter_context(patch("stratus.terminal.pty_session.os.close"))
            stack.enter_context(
                patch("stratus.terminal.pty_session.os.waitpid", return_value=(12345, 0))
            )
            stack.enter_context(
                patch("stratus.terminal.pty_session.termios.tcgetattr", return_value=[0] * 7)
            )
            stack.enter_context(patch("stratus.terminal.pty_session.termios.tcsetattr"))
            stack.enter_context(patch("stratus.terminal.pty_session.fcntl.ioctl"))

            mock_loop = MagicMock()
            stack.enter_context(patch("asyncio.get_running_loop", return_value=mock_loop))

            from stratus.terminal.pty_session import PTYSession

            session = PTYSession(cols=80, rows=24)
            await session.start()

            await session.close()

            mock_kill.assert_called_with(12345, signal.SIGHUP)
            mock_close.assert_called_with(10)
            assert session.master_fd is None

    @pytest.mark.asyncio
    async def test_close_sends_sigkill_on_sighup_failure(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch("stratus.terminal.pty_session.pty.fork", return_value=(12345, 10))
            )
            stack.enter_context(patch("stratus.terminal.pty_session.os.set_blocking"))
            mock_kill = stack.enter_context(patch("stratus.terminal.pty_session.os.kill"))
            stack.enter_context(patch("stratus.terminal.pty_session.os.close"))
            stack.enter_context(
                patch("stratus.terminal.pty_session.os.waitpid", return_value=(0, 0))
            )
            stack.enter_context(
                patch("stratus.terminal.pty_session.termios.tcgetattr", return_value=[0] * 7)
            )
            stack.enter_context(patch("stratus.terminal.pty_session.termios.tcsetattr"))
            stack.enter_context(patch("stratus.terminal.pty_session.fcntl.ioctl"))

            mock_loop = MagicMock()
            stack.enter_context(patch("asyncio.get_running_loop", return_value=mock_loop))

            from stratus.terminal.pty_session import PTYSession

            session = PTYSession(cols=80, rows=24)
            await session.start()

            mock_kill.side_effect = [ProcessLookupError(), None]
            await session.close()

            assert mock_kill.call_count == 2
            mock_kill.assert_any_call(12345, signal.SIGHUP)
            mock_kill.assert_any_call(12345, signal.SIGKILL)

    @pytest.mark.asyncio
    async def test_close_cleans_up_fd(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch("stratus.terminal.pty_session.pty.fork", return_value=(12345, 10))
            )
            stack.enter_context(patch("stratus.terminal.pty_session.os.set_blocking"))
            stack.enter_context(patch("stratus.terminal.pty_session.os.kill"))
            mock_close = stack.enter_context(patch("stratus.terminal.pty_session.os.close"))
            stack.enter_context(
                patch("stratus.terminal.pty_session.os.waitpid", return_value=(0, 0))
            )
            stack.enter_context(
                patch("stratus.terminal.pty_session.termios.tcgetattr", return_value=[0] * 7)
            )
            stack.enter_context(patch("stratus.terminal.pty_session.termios.tcsetattr"))
            stack.enter_context(patch("stratus.terminal.pty_session.fcntl.ioctl"))

            mock_loop = MagicMock()
            stack.enter_context(patch("asyncio.get_running_loop", return_value=mock_loop))

            from stratus.terminal.pty_session import PTYSession

            session = PTYSession(cols=80, rows=24)
            await session.start()

            await session.close()

            assert session.master_fd is None
            mock_close.assert_called_once_with(10)

    @pytest.mark.asyncio
    async def test_double_close_safe(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch("stratus.terminal.pty_session.pty.fork", return_value=(12345, 10))
            )
            stack.enter_context(patch("stratus.terminal.pty_session.os.set_blocking"))
            mock_kill = stack.enter_context(patch("stratus.terminal.pty_session.os.kill"))
            mock_close = stack.enter_context(patch("stratus.terminal.pty_session.os.close"))
            stack.enter_context(
                patch("stratus.terminal.pty_session.os.waitpid", return_value=(0, 0))
            )
            stack.enter_context(
                patch("stratus.terminal.pty_session.termios.tcgetattr", return_value=[0] * 7)
            )
            stack.enter_context(patch("stratus.terminal.pty_session.termios.tcsetattr"))
            stack.enter_context(patch("stratus.terminal.pty_session.fcntl.ioctl"))

            mock_loop = MagicMock()
            stack.enter_context(patch("asyncio.get_running_loop", return_value=mock_loop))

            from stratus.terminal.pty_session import PTYSession

            session = PTYSession(cols=80, rows=24)
            await session.start()
            await session.close()

            mock_kill.reset_mock()
            mock_close.reset_mock()

            await session.close()

            mock_kill.assert_not_called()
            mock_close.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_removes_reader(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch("stratus.terminal.pty_session.pty.fork", return_value=(12345, 10))
            )
            stack.enter_context(patch("stratus.terminal.pty_session.os.set_blocking"))
            stack.enter_context(patch("stratus.terminal.pty_session.os.kill"))
            stack.enter_context(patch("stratus.terminal.pty_session.os.close"))
            stack.enter_context(
                patch("stratus.terminal.pty_session.os.waitpid", return_value=(0, 0))
            )
            stack.enter_context(
                patch("stratus.terminal.pty_session.termios.tcgetattr", return_value=[0] * 7)
            )
            stack.enter_context(patch("stratus.terminal.pty_session.termios.tcsetattr"))
            stack.enter_context(patch("stratus.terminal.pty_session.fcntl.ioctl"))

            mock_loop = MagicMock()
            stack.enter_context(patch("asyncio.get_running_loop", return_value=mock_loop))

            from stratus.terminal.pty_session import PTYSession

            session = PTYSession(cols=80, rows=24)
            await session.start()

            await session.close()

            mock_loop.remove_reader.assert_called_once_with(10)


class TestPTYSessionOutput:
    @pytest.mark.asyncio
    async def test_output_queue_receives_data(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch("stratus.terminal.pty_session.pty.fork", return_value=(12345, 10))
            )
            stack.enter_context(patch("stratus.terminal.pty_session.os.set_blocking"))
            stack.enter_context(
                patch("stratus.terminal.pty_session.termios.tcgetattr", return_value=[0] * 7)
            )
            stack.enter_context(patch("stratus.terminal.pty_session.termios.tcsetattr"))
            stack.enter_context(patch("stratus.terminal.pty_session.fcntl.ioctl"))

            mock_loop = MagicMock()
            stack.enter_context(patch("asyncio.get_running_loop", return_value=mock_loop))

            from stratus.terminal.pty_session import PTYSession

            session = PTYSession(cols=80, rows=24)
            await session.start()

            mock_loop.add_reader.assert_called_once_with(10, session._read_callback)

    @pytest.mark.asyncio
    async def test_read_output_returns_data(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch("stratus.terminal.pty_session.pty.fork", return_value=(12345, 10))
            )
            stack.enter_context(patch("stratus.terminal.pty_session.os.set_blocking"))
            stack.enter_context(
                patch("stratus.terminal.pty_session.termios.tcgetattr", return_value=[0] * 7)
            )
            stack.enter_context(patch("stratus.terminal.pty_session.termios.tcsetattr"))
            stack.enter_context(patch("stratus.terminal.pty_session.fcntl.ioctl"))

            mock_loop = MagicMock()
            stack.enter_context(patch("asyncio.get_running_loop", return_value=mock_loop))

            from stratus.terminal.pty_session import PTYSession

            session = PTYSession(cols=80, rows=24)
            await session.start()

            await session._output_queue.put(b"test output")

            data = await asyncio.wait_for(session.read_output(), timeout=1.0)
            assert data == b"test output"

    @pytest.mark.asyncio
    async def test_read_output_raises_when_not_started(self):
        from stratus.terminal.pty_session import PTYSession

        session = PTYSession(cols=80, rows=24)

        with pytest.raises(RuntimeError, match="PTY not started"):
            await session.read_output()


class TestPTYSessionExitDetection:
    @pytest.mark.asyncio
    async def test_exit_detected_sets_active_false(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch("stratus.terminal.pty_session.pty.fork", return_value=(12345, 10))
            )
            stack.enter_context(patch("stratus.terminal.pty_session.os.set_blocking"))
            mock_waitpid = stack.enter_context(
                patch("stratus.terminal.pty_session.os.waitpid", return_value=(12345, 0))
            )
            stack.enter_context(
                patch("stratus.terminal.pty_session.termios.tcgetattr", return_value=[0] * 7)
            )
            stack.enter_context(patch("stratus.terminal.pty_session.termios.tcsetattr"))
            stack.enter_context(patch("stratus.terminal.pty_session.fcntl.ioctl"))

            mock_loop = MagicMock()
            stack.enter_context(patch("asyncio.get_running_loop", return_value=mock_loop))

            from stratus.terminal.pty_session import PTYSession

            session = PTYSession(cols=80, rows=24)
            await session.start()

            session._check_exit()

            assert session.active is False


class TestPTYSessionProperties:
    def test_cols_rows_initial(self):
        from stratus.terminal.pty_session import PTYSession

        session = PTYSession(cols=120, rows=40)
        assert session.cols == 120
        assert session.rows == 40

    def test_shell_default(self):
        from stratus.terminal.pty_session import PTYSession

        session = PTYSession(cols=80, rows=24)
        assert session.shell in ["/bin/bash", os.environ.get("SHELL", "/bin/bash")]

    def test_shell_custom(self):
        from stratus.terminal.pty_session import PTYSession

        session = PTYSession(cols=80, rows=24, shell="/bin/zsh")
        assert session.shell == "/bin/zsh"

    def test_is_running_false_before_start(self):
        from stratus.terminal.pty_session import PTYSession

        session = PTYSession(cols=80, rows=24)
        assert session.is_running is False

    @pytest.mark.asyncio
    async def test_is_running_true_after_start(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch("stratus.terminal.pty_session.pty.fork", return_value=(12345, 10))
            )
            stack.enter_context(patch("stratus.terminal.pty_session.os.set_blocking"))
            stack.enter_context(
                patch("stratus.terminal.pty_session.termios.tcgetattr", return_value=[0] * 7)
            )
            stack.enter_context(patch("stratus.terminal.pty_session.termios.tcsetattr"))
            stack.enter_context(patch("stratus.terminal.pty_session.fcntl.ioctl"))

            mock_loop = MagicMock()
            stack.enter_context(patch("asyncio.get_running_loop", return_value=mock_loop))

            from stratus.terminal.pty_session import PTYSession

            session = PTYSession(cols=80, rows=24)
            await session.start()

            assert session.is_running is True

    @pytest.mark.asyncio
    async def test_is_running_false_after_close(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch("stratus.terminal.pty_session.pty.fork", return_value=(12345, 10))
            )
            stack.enter_context(patch("stratus.terminal.pty_session.os.set_blocking"))
            stack.enter_context(patch("stratus.terminal.pty_session.os.kill"))
            stack.enter_context(patch("stratus.terminal.pty_session.os.close"))
            stack.enter_context(
                patch("stratus.terminal.pty_session.os.waitpid", return_value=(0, 0))
            )
            stack.enter_context(
                patch("stratus.terminal.pty_session.termios.tcgetattr", return_value=[0] * 7)
            )
            stack.enter_context(patch("stratus.terminal.pty_session.termios.tcsetattr"))
            stack.enter_context(patch("stratus.terminal.pty_session.fcntl.ioctl"))

            mock_loop = MagicMock()
            stack.enter_context(patch("asyncio.get_running_loop", return_value=mock_loop))

            from stratus.terminal.pty_session import PTYSession

            session = PTYSession(cols=80, rows=24)
            await session.start()
            await session.close()

            assert session.is_running is False


class TestPTYSessionContextManager:
    @pytest.mark.asyncio
    async def test_context_manager_closes_on_exit(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch("stratus.terminal.pty_session.pty.fork", return_value=(12345, 10))
            )
            stack.enter_context(patch("stratus.terminal.pty_session.os.set_blocking"))
            stack.enter_context(patch("stratus.terminal.pty_session.os.kill"))
            mock_close = stack.enter_context(patch("stratus.terminal.pty_session.os.close"))
            stack.enter_context(
                patch("stratus.terminal.pty_session.os.waitpid", return_value=(0, 0))
            )
            stack.enter_context(
                patch("stratus.terminal.pty_session.termios.tcgetattr", return_value=[0] * 7)
            )
            stack.enter_context(patch("stratus.terminal.pty_session.termios.tcsetattr"))
            stack.enter_context(patch("stratus.terminal.pty_session.fcntl.ioctl"))

            mock_loop = MagicMock()
            stack.enter_context(patch("asyncio.get_running_loop", return_value=mock_loop))

            from stratus.terminal.pty_session import PTYSession

            async with PTYSession(cols=80, rows=24) as session:
                assert session.is_running is True

            assert session.is_running is False
            mock_close.assert_called()
