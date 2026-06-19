"""
pipeline/barge_in.py

BargeInController — thread-safe flag that signals in-flight LLM + TTS
streams to stop when the user starts speaking mid-response.

How to wire it up in your WebSocket gateway:

    pipeline = S2SPipeline(session_id=sid)

    # In your VAD callback (runs in a separate task):
    async def on_speech_start():
        pipeline.barge_in.trigger()

    # The orchestrator checks barge_in.triggered at each yield point
    async for audio in pipeline.run(audio_bytes):
        await ws.send_bytes(audio)
"""

from __future__ import annotations

import asyncio
import time
from shared.logging import get_logger

logger = get_logger(__name__)


class BargeInController:
    """
    Lightweight async-safe flag.
    trigger() sets it from any coroutine or thread.
    reset()   clears it at the start of each new turn.
    """

    def __init__(self) -> None:
        self._triggered: bool = False
        self._triggered_at: float | None = None
        self._lock = asyncio.Lock()

    @property
    def triggered(self) -> bool:
        return self._triggered

    async def trigger(self, session_id: str = "") -> None:
        """
        Signal that the user has started speaking.
        Safe to call from the VAD handler while the pipeline is yielding.
        """
        async with self._lock:
            if not self._triggered:
                self._triggered = True
                self._triggered_at = time.perf_counter()
                logger.info(f"[barge-in] Triggered for session '{session_id}'")

    def trigger_sync(self, session_id: str = "") -> None:
        """
        Synchronous version — use from non-async VAD callbacks.
        Not lock-protected but safe in practice (boolean write is atomic in CPython).
        """
        if not self._triggered:
            self._triggered = True
            self._triggered_at = time.perf_counter()
            logger.info(f"[barge-in] Triggered (sync) for session '{session_id}'")

    def reset(self) -> None:
        """Call at the start of each pipeline.run() turn."""
        self._triggered = False
        self._triggered_at = None

    @property
    def latency_ms(self) -> float | None:
        """How many ms ago barge-in was triggered (for metrics)."""
        if self._triggered_at is None:
            return None
        return (time.perf_counter() - self._triggered_at) * 1000
