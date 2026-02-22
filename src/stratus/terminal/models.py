from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class WSMessageType(StrEnum):
    INPUT = "input"
    RESIZE = "resize"
    CREATE = "create"
    PING = "ping"


class WSServerMessageType(StrEnum):
    CREATED = "created"
    OUTPUT = "output"
    EXIT = "exit"
    ERROR = "error"
    PONG = "pong"


class WSMessage(BaseModel):
    type: WSMessageType
    session_id: str | None = None
    data: str | None = None
    cols: int | None = None
    rows: int | None = None
    cwd: str | None = None

    @model_validator(mode="after")
    def validate_message(self):
        if self.type == WSMessageType.INPUT:
            if self.data is None:
                raise ValueError("data is required for input messages")
        elif self.type == WSMessageType.RESIZE:
            if self.cols is None or self.rows is None:
                raise ValueError("cols and rows are required for resize messages")
        elif self.type == WSMessageType.CREATE:
            if self.cols is None:
                self.cols = 80
            if self.rows is None:
                self.rows = 24
        return self

    @model_validator(mode="before")
    @classmethod
    def set_defaults(cls, data):
        if isinstance(data, dict):
            if data.get("type") == "create":
                data.setdefault("cols", 80)
                data.setdefault("rows", 24)
        return data


class WSServerMessage(BaseModel):
    type: WSServerMessageType
    session_id: str | None = None
    data: str | None = None
    shell: str | None = None
    cwd: str | None = None
    code: int | None = None
    message: str | None = None

    @model_validator(mode="after")
    def set_error_code(self):
        if self.type == WSServerMessageType.ERROR and self.code is None:
            self.code = 500
        return self


class TerminalSession(BaseModel):
    id: str
    pid: int
    master_fd: int
    cols: int
    rows: int
    shell: str
    cwd: str
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
