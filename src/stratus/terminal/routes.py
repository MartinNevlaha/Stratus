from __future__ import annotations

import asyncio
import json
import logging
import os

from starlette.endpoints import HTTPEndpoint
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket

from stratus.terminal.config import TerminalConfig
from stratus.terminal.manager import TerminalManager
from stratus.terminal.models import WSServerMessage, WSServerMessageType

logger = logging.getLogger(__name__)

MIN_COLS, MAX_COLS = 1, 500
MIN_ROWS, MAX_ROWS = 1, 200
ALLOWED_ORIGINS = {"http://127.0.0.1:41777", "http://localhost:41777"}


def validate_dimensions(cols: int, rows: int) -> tuple[int, int]:
    return (
        max(MIN_COLS, min(MAX_COLS, cols)),
        max(MIN_ROWS, min(MAX_ROWS, rows)),
    )


def validate_cwd(cwd: str | None) -> str | None:
    if cwd is None:
        return None
    resolved = os.path.realpath(cwd)
    if not os.path.isdir(resolved):
        raise ValueError(f"Directory does not exist: {cwd}")
    return resolved


class TerminalStatus(HTTPEndpoint):
    async def get(self, request) -> JSONResponse:
        config: TerminalConfig = getattr(request.app.state, "terminal_config", TerminalConfig())
        return JSONResponse(
            {
                "enabled": config.enabled,
                "max_sessions": config.max_sessions,
            }
        )


class TerminalSessions(HTTPEndpoint):
    async def get(self, request) -> JSONResponse:
        manager: TerminalManager = request.app.state.terminal_manager
        sessions = manager.list_sessions()
        return JSONResponse(
            {
                "sessions": sessions,
                "count": len(sessions),
            }
        )


async def terminal_websocket(websocket: WebSocket):
    origin = websocket.headers.get("origin", "")
    host = websocket.headers.get("host", "")
    allowed = (
        not origin
        or origin in ALLOWED_ORIGINS
        or origin == f"http://{host}"
        or origin == f"https://{host}"
    )
    if not allowed:
        logger.warning(f"Rejected WebSocket from origin: {origin}")
        await websocket.close(code=1008, reason="Origin not allowed")
        return

    await websocket.accept()

    manager: TerminalManager = websocket.app.state.terminal_manager
    current_session_id: str | None = None
    output_task: asyncio.Task | None = None

    async def send_output(session_id: str):
        pty = manager.get_session(session_id)
        if not pty:
            return

        try:
            while pty.is_running:
                try:
                    data = await asyncio.wait_for(pty.read_output(), timeout=0.1)
                    msg = WSServerMessage(
                        type=WSServerMessageType.OUTPUT,
                        session_id=session_id,
                        data=data.decode("utf-8", errors="replace"),
                    )
                    await websocket.send_json(msg.model_dump())
                except TimeoutError:
                    continue
                except Exception as e:
                    logger.exception("Output loop error: %s", e)
                    break
        except asyncio.CancelledError:
            pass

        if not pty.active:
            try:
                msg = WSServerMessage(type=WSServerMessageType.EXIT, session_id=session_id, code=0)
                await websocket.send_json(msg.model_dump())
            except Exception:
                pass

    try:
        while True:
            try:
                raw_data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                data = json.loads(raw_data)
            except TimeoutError:
                continue
            except json.JSONDecodeError:
                msg = WSServerMessage(type=WSServerMessageType.ERROR, message="Invalid JSON")
                await websocket.send_json(msg.model_dump())
                continue

            try:
                if data.get("type") == "ping":
                    msg = WSServerMessage(type=WSServerMessageType.PONG)
                    await websocket.send_json(msg.model_dump())
                    continue

                if data.get("type") == "create":
                    try:
                        cols = int(data.get("cols", 80))
                        rows = int(data.get("rows", 24))
                        cols, rows = validate_dimensions(cols, rows)

                        cwd = data.get("cwd")
                        cwd = validate_cwd(cwd)

                        session_id = await manager.create_session(cols=cols, rows=rows, cwd=cwd)
                        current_session_id = session_id
                        pty = manager.get_session(session_id)

                        if pty is None:
                            msg = WSServerMessage(
                                type=WSServerMessageType.ERROR, message="Failed to create session"
                            )
                            await websocket.send_json(msg.model_dump())
                            continue

                        output_task = asyncio.create_task(send_output(session_id))

                        msg = WSServerMessage(
                            type=WSServerMessageType.CREATED,
                            session_id=session_id,
                            shell=pty.shell,
                            cwd=pty.cwd,
                        )
                        await websocket.send_json(msg.model_dump())
                        logger.info(f"Terminal session created: {session_id[:8]}...")
                    except (ValueError, RuntimeError) as e:
                        msg = WSServerMessage(type=WSServerMessageType.ERROR, message=str(e))
                        await websocket.send_json(msg.model_dump())
                    continue

                if data.get("type") == "input":
                    session_id = data.get("session_id")
                    input_data = data.get("data", "")

                    pty = manager.get_session(session_id)
                    if not pty:
                        msg = WSServerMessage(
                            type=WSServerMessageType.ERROR, message="Session not found", code=404
                        )
                        await websocket.send_json(msg.model_dump())
                        continue

                    await pty.write(input_data.encode("utf-8"))
                    continue

                if data.get("type") == "resize":
                    session_id = data.get("session_id")
                    cols = int(data.get("cols", 80))
                    rows = int(data.get("rows", 24))
                    cols, rows = validate_dimensions(cols, rows)

                    pty = manager.get_session(session_id)
                    if not pty:
                        msg = WSServerMessage(
                            type=WSServerMessageType.ERROR, message="Session not found", code=404
                        )
                        await websocket.send_json(msg.model_dump())
                        continue

                    await pty.resize(cols, rows)
                    continue

                msg = WSServerMessage(
                    type=WSServerMessageType.ERROR,
                    message=f"Unknown message type: {data.get('type')}",
                )
                await websocket.send_json(msg.model_dump())

            except Exception as e:
                logger.exception("WebSocket message error: %s", e)
                msg = WSServerMessage(type=WSServerMessageType.ERROR, message=str(e))
                await websocket.send_json(msg.model_dump())

    except Exception as e:
        logger.exception("WebSocket error: %s", e)
    finally:
        if output_task:
            output_task.cancel()
            try:
                await output_task
            except asyncio.CancelledError:
                pass

        if current_session_id:
            await manager.destroy_session(current_session_id)
            logger.info(f"Terminal session destroyed: {current_session_id[:8]}...")


routes = [
    Route("/api/terminal/status", TerminalStatus),
    Route("/api/terminal/sessions", TerminalSessions),
    WebSocketRoute("/api/terminal/ws", terminal_websocket),
]
