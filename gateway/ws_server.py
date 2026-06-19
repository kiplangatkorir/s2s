"""FastAPI WebSocket gateway for the S2S pipeline."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from pipeline.orchestrator import S2SPipeline


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

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        session_id = websocket.query_params.get("session_id") or str(uuid.uuid4())
        pipeline = get_pipeline(session_id)
        audio_buffer = bytearray()

        try:
            while True:
                message = await websocket.receive()

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

                if payload.get("type") == "end_turn":
                    if not audio_buffer:
                        await websocket.send_json({"type": "empty_turn"})
                        continue

                    audio_bytes = bytes(audio_buffer)
                    audio_buffer.clear()

                    try:
                        async for chunk in pipeline.run(audio_bytes):
                            if isinstance(chunk, dict):
                                await websocket.send_json(chunk)
                            else:
                                await websocket.send_bytes(chunk)
                    except Exception as exc:
                        await websocket.send_json({"type": "error", "detail": str(exc)})
                        continue

                    await websocket.send_json({"type": "turn_complete", "session_id": session_id})
                    continue

                if payload.get("type") == "text_input":
                    text = payload.get("text", "").strip()
                    if not text:
                        await websocket.send_json({"type": "empty_turn"})
                        continue

                    audio_buffer.clear()

                    try:
                        async for chunk in pipeline.run_text(text):
                            if isinstance(chunk, dict):
                                await websocket.send_json(chunk)
                            else:
                                await websocket.send_bytes(chunk)
                    except Exception as exc:
                        await websocket.send_json({"type": "error", "detail": str(exc)})
                        continue

                    await websocket.send_json({"type": "turn_complete", "session_id": session_id})
                    continue

                await websocket.send_json({"type": "ack", "detail": payload})
        except WebSocketDisconnect:
            sessions.pop(session_id, None)
            return

    return app


app = create_app()
