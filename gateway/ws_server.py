"""FastAPI WebSocket gateway for the S2S pipeline."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from pipeline.orchestrator import S2SPipeline

HEARTBEAT_INTERVAL_S = 8
RECEIVE_TIMEOUT_S = 45


def create_app(
    pipeline_factory: Callable[[str], object] | None = None,
) -> FastAPI:
    """Create the FastAPI app used by the client-facing gateway."""
    app = FastAPI(title="Sauti S2S Gateway")
    sessions: dict[str, object] = {}

    def get_pipeline(session_id: str) -> object:
        existing = sessions.get(session_id)
        if existing is not None:
            return existing

        factory = pipeline_factory or (lambda sid: S2SPipeline(session_id=sid))
        created = factory(session_id)
        sessions[session_id] = created
        return created

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    async def _heartbeat(ws: WebSocket, pong_received: asyncio.Event) -> None:
        """Send pings every HEARTBEAT_INTERVAL_S. If no pong within 2 intervals, close."""
        missed = 0
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL_S)
                pong_received.clear()
                await ws.send_json({"type": "ping"})
                try:
                    await asyncio.wait_for(pong_received.wait(), timeout=HEARTBEAT_INTERVAL_S * 2)
                    missed = 0
                except asyncio.TimeoutError:
                    missed += 1
                    if missed >= 2:
                        await ws.close(code=1001, reason="heartbeat_timeout")
                        return
        except (WebSocketDisconnect, RuntimeError, Exception):
            pass

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        session_id = websocket.query_params.get("session_id") or str(uuid.uuid4())
        pipeline = get_pipeline(session_id)
        audio_buffer = bytearray()

        pong_received = asyncio.Event()
        heartbeat_task = asyncio.create_task(_heartbeat(websocket, pong_received))

        try:
            while True:
                try:
                    message = await asyncio.wait_for(
                        websocket.receive(), timeout=RECEIVE_TIMEOUT_S
                    )
                except asyncio.TimeoutError:
                    await websocket.close(code=1001, reason="receive_timeout")
                    break

                if message.get("type") == "websocket.disconnect":
                    break

                if message.get("bytes") is not None and message["bytes"]:
                    audio_buffer.extend(message["bytes"])
                    continue

                if message.get("text") is None:
                    continue

                try:
                    payload = json.loads(message["text"])
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "detail": "invalid_json"})
                    continue

                if payload.get("type") == "pong":
                    pong_received.set()
                    continue

                if payload.get("type") == "end_turn":
                    if not audio_buffer:
                        await websocket.send_json({"type": "empty_turn"})
                        continue

                    audio_bytes = bytes(audio_buffer)
                    audio_buffer.clear()
                    asyncio.create_task(
                        _run_pipeline_turn(pipeline, audio_bytes, websocket, session_id)
                    )
                    continue

                if payload.get("type") == "text_input":
                    text = payload.get("text", "").strip()
                    if not text:
                        await websocket.send_json({"type": "empty_turn"})
                        continue

                    audio_buffer.clear()
                    asyncio.create_task(
                        _run_text_turn(pipeline, text, websocket, session_id)
                    )
                    continue

                await websocket.send_json({"type": "ack", "detail": payload})
        except WebSocketDisconnect:
            heartbeat_task.cancel()
            sessions.pop(session_id, None)
            return

    async def _run_pipeline_turn(
        pipeline: object,
        audio_bytes: bytes,
        ws: WebSocket,
        session_id: str,
    ) -> None:
        try:
            async for chunk in pipeline.run(audio_bytes):
                if isinstance(chunk, dict):
                    await ws.send_json(chunk)
                else:
                    await ws.send_bytes(chunk)
        except Exception as exc:
            try:
                await ws.send_json({"type": "error", "detail": str(exc)})
            except (WebSocketDisconnect, RuntimeError):
                return
        try:
            await ws.send_json({"type": "turn_complete", "session_id": session_id})
        except (WebSocketDisconnect, RuntimeError):
            pass

    async def _run_text_turn(
        pipeline: object,
        text: str,
        ws: WebSocket,
        session_id: str,
    ) -> None:
        try:
            async for chunk in pipeline.run_text(text):
                if isinstance(chunk, dict):
                    await ws.send_json(chunk)
                else:
                    await ws.send_bytes(chunk)
        except Exception as exc:
            try:
                await ws.send_json({"type": "error", "detail": str(exc)})
            except (WebSocketDisconnect, RuntimeError):
                return
        try:
            await ws.send_json({"type": "turn_complete", "session_id": session_id})
        except (WebSocketDisconnect, RuntimeError):
            pass

    return app


app = create_app()
