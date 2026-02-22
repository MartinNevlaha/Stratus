from __future__ import annotations

import asyncio
import fcntl
import logging
import os
import pty
import signal
import struct
import sys
import termios
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

MAX_QUEUE_SIZE = 65536
SUPPORTED_PLATFORMS = ("linux", "darwin")


def check_platform() -> None:
    if sys.platform not in SUPPORTED_PLATFORMS:
        raise RuntimeError(f"PTY not supported on {sys.platform}. Unix-only feature.")


@dataclass
class PTYSession:
    cols: int = 80
    rows: int = 24
    shell: str | None = None
    cwd: str | None = None

    pid: int | None = field(default=None, init=False)
    master_fd: int | None = field(default=None, init=False)
    active: bool = field(default=True, init=False)
    _closed: bool = field(default=False, init=False)
    _output_queue: asyncio.Queue[bytes] = field(
        default_factory=lambda: asyncio.Queue(maxsize=MAX_QUEUE_SIZE), init=False
    )
    _loop: asyncio.AbstractEventLoop | None = field(default=None, init=False)

    def __post_init__(self):
        if self.shell is None:
            self.shell = os.environ.get("SHELL", "/bin/bash")
        if self.cwd is None:
            self.cwd = os.getcwd()

    @property
    def is_running(self) -> bool:
        return self.master_fd is not None and self.active

    async def start(self) -> None:
        check_platform()

        def child_process():
            if self.cwd:
                os.chdir(self.cwd)
            os.environ["TERM"] = "xterm-256color"
            if self.shell:
                os.execvp(self.shell, [self.shell])

        self.pid, self.master_fd = pty.fork()

        if self.pid == 0:
            child_process()

        os.set_blocking(self.master_fd, False)

        self._set_winsize(self.cols, self.rows)

        self._loop = asyncio.get_running_loop()
        self._loop.add_reader(self.master_fd, self._read_callback)
        logger.debug(f"PTY session started: pid={self.pid}")

    def _set_winsize(self, cols: int, rows: int) -> None:
        if self.master_fd is None:
            return
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        try:
            termios.tcsetattr(self.master_fd, termios.TCSANOW, termios.tcgetattr(self.master_fd))
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
        except OSError as e:
            logger.warning(f"Failed to set winsize: {e}")

    def _read_callback(self) -> None:
        if self.master_fd is None:
            return
        try:
            data = os.read(self.master_fd, 65536)
            if data:
                if self._output_queue.full():
                    try:
                        self._output_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                asyncio.ensure_future(self._output_queue.put(data))
            else:
                self._check_exit()
        except BlockingIOError:
            pass
        except OSError:
            self._check_exit()

    def _check_exit(self) -> None:
        if self.pid is None:
            return
        try:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
            if pid == self.pid:
                self.active = False
                logger.debug(f"PTY process exited: pid={self.pid}, status={status}")
        except ChildProcessError:
            self.active = False

    async def write(self, data: bytes) -> None:
        if self.master_fd is None:
            raise RuntimeError("PTY not started")
        os.write(self.master_fd, data)

    async def read_output(self) -> bytes:
        if self.master_fd is None:
            raise RuntimeError("PTY not started")
        return await self._output_queue.get()

    async def resize(self, cols: int, rows: int) -> None:
        if self.master_fd is None:
            raise RuntimeError("PTY not started")
        self.cols = cols
        self.rows = rows
        self._set_winsize(cols, rows)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        master_fd = self.master_fd
        pid = self.pid
        self.master_fd = None
        self.active = False

        if self._loop and master_fd is not None:
            try:
                self._loop.remove_reader(master_fd)
            except Exception as e:
                logger.warning(f"Failed to remove reader: {e}")

        if pid is not None:
            try:
                os.kill(pid, signal.SIGHUP)
            except ProcessLookupError:
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
            except OSError:
                pass

            for _ in range(10):
                try:
                    wpid, _ = os.waitpid(pid, os.WNOHANG)
                    if wpid == pid:
                        break
                except ChildProcessError:
                    break
                await asyncio.sleep(0.1)

        if master_fd is not None:
            try:
                os.close(master_fd)
            except OSError as e:
                logger.warning(f"Failed to close master_fd: {e}")

        logger.debug(f"PTY session closed: pid={pid}")

    async def __aenter__(self) -> PTYSession:
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
