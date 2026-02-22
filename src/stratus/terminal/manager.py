from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field

from stratus.terminal.config import TerminalConfig
from stratus.terminal.pty_session import PTYSession


@dataclass
class TerminalManager:
    config: TerminalConfig = field(default_factory=TerminalConfig)
    _sessions: dict[str, PTYSession] = field(default_factory=dict)
    _valid_tokens: set[str] = field(default_factory=set)

    def _generate_token(self) -> str:
        token = secrets.token_urlsafe(32)
        self._valid_tokens.add(token)
        return token

    def validate_token(self, token: str) -> bool:
        return token in self._valid_tokens

    async def _create_pty(self, cols: int, rows: int, cwd: str | None = None) -> PTYSession:
        shell = self.config.default_shell
        if cwd is None:
            cwd = os.getcwd()

        pty = PTYSession(cols=cols, rows=rows, shell=shell, cwd=cwd)
        await pty.start()
        return pty

    async def create_session(
        self, cols: int | None = None, rows: int | None = None, cwd: str | None = None
    ) -> str:
        if len(self._sessions) >= self.config.max_sessions:
            raise RuntimeError(f"Maximum sessions ({self.config.max_sessions}) reached")

        if cols is None:
            cols = self.config.default_cols
        if rows is None:
            rows = self.config.default_rows

        session_id = secrets.token_urlsafe(12)
        pty = await self._create_pty(cols, rows, cwd)

        self._sessions[session_id] = pty
        return session_id

    def get_session(self, session_id: str) -> PTYSession | None:
        return self._sessions.get(session_id)

    async def destroy_session(self, session_id: str) -> None:
        pty = self._sessions.pop(session_id, None)
        if pty is not None:
            await pty.close()

    async def cleanup_all(self) -> None:
        session_ids = list(self._sessions.keys())
        for session_id in session_ids:
            await self.destroy_session(session_id)

    def list_sessions(self) -> list[dict]:
        result = []
        for session_id, pty in self._sessions.items():
            result.append(
                {
                    "id": session_id,
                    "pid": pty.pid,
                    "cols": pty.cols,
                    "rows": pty.rows,
                    "shell": pty.shell,
                    "cwd": pty.cwd,
                    "active": pty.active,
                }
            )
        return result
