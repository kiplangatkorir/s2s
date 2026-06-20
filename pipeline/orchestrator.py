"""
pipeline/orchestrator.py

MsingiAI S2S Pipeline Orchestrator
Coordinates: Sauti ASR → DeepSeek V4 → Sauti TTS
All stages stream concurrently — TTS starts before LLM finishes.

Usage (from your WebSocket gateway):
    pipeline = S2SPipeline(session_id="abc123")
    async for audio_chunk in pipeline.run(audio_bytes, language="sw"):
        await ws.send_bytes(audio_chunk)
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import AsyncGenerator

import modal

from pipeline.sentence_splitter import SentenceSplitter
from pipeline.barge_in import BargeInController
from pipeline.session import Session
from pipeline.context_manager import ContextManager
from shared.metrics import LatencyTracker
from shared.schemas import TranscriptResult, TTSRequest
from shared.logging import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────
# Modal function references
# (imported lazily so local dev doesn't require Modal auth)
# ─────────────────────────────────────────

def _get_asr() -> modal.Cls:
    SautiASR = modal.Cls.from_name("msingiai-sauti-asr", "SautiASR")
    return SautiASR()

def _get_tts() -> modal.Cls:
    SautiTTS = modal.Cls.from_name("msingiai-sauti-tts", "SautiTTS")
    return SautiTTS()


# ─────────────────────────────────────────
# Pipeline config
# ─────────────────────────────────────────

@dataclass
class PipelineConfig:
    language: str = "sw"                  # ASR + TTS language
    deepseek_model: str = "deepseek-v4-flash"
    max_history_tokens: int = 768         # tighter prompt budget for lower TTFT
    tts_chunk_size: int = 55             # balance: starts TTS sooner, still fewer calls than 25
    stream_timeout_s: float = 30.0       # max seconds for a full turn
    system_prompt: str = (
        "You are Sauti, a warm and friendly voice assistant built by MsingiAI. "
        "You speak naturally and conversationally. "
        "Always reply in the same language the user speaks — primarily Swahili or English. "
        "Keep responses short (1–3 sentences) since they will be read aloud. "
        "Use natural spoken language: contractions, simple words, and a friendly tone. "
        "Never use markdown, bullet points, numbered lists, code blocks, or any formatting that doesn't sound natural when spoken. "
        "If the user asks something complex, give a brief answer and offer to explain more. "
        "Spell out numbers in words (e.g. 'twenty three' not '23'). "
        "Avoid abbreviations, URLs, and special characters."
    )


# ─────────────────────────────────────────
# Main pipeline class
# ─────────────────────────────────────────

class S2SPipeline:
    """
    One instance per user session.
    Call run() for each user utterance — yields raw PCM audio bytes
    that can be streamed directly to the client.
    """

    def __init__(
        self,
        session_id: str | None = None,
        config: PipelineConfig | None = None,
    ):
        self.session_id = session_id or str(uuid.uuid4())
        self.config = config or PipelineConfig()
        self.session = Session(self.session_id)
        self.context = ContextManager(
            max_tokens=self.config.max_history_tokens,
            system_prompt=self.config.system_prompt,
        )
        self.barge_in = BargeInController()
        self._asr = None
        self._tts = None

    # ── lazy Modal handles ──────────────────

    @property
    def asr(self):
        if self._asr is None:
            self._asr = _get_asr()
        return self._asr

    @property
    def tts(self):
        if self._tts is None:
            self._tts = _get_tts()
        return self._tts

    # ── main entry point ────────────────────

    async def run(
        self,
        audio_bytes: bytes,
        language: str | None = None,
    ) -> AsyncGenerator[bytes | dict, None]:
        """
        Full S2S turn:
          1. ASR   — stream partial transcripts while audio arrives
          2. LLM   — stream tokens from DeepSeek V4 as transcript finalises
          3. TTS   — stream audio chunks as LLM phrases complete

        Yields raw PCM playback bytes from TTS and text_delta dicts.
        Call barge_in.trigger() from your VAD handler to cancel mid-turn.
        """
        lang = language or self.config.language
        tracker = LatencyTracker(session_id=self.session_id)
        self.barge_in.reset()

        tracker.mark("pipeline_start")

        try:
            # ── Stage 1: ASR ────────────────────────
            transcript = await self._run_asr(audio_bytes, lang, tracker)

            if not transcript or self.barge_in.triggered:
                logger.info(f"[{self.session_id}] Barge-in or empty transcript, aborting.")
                return

            logger.info(f"[{self.session_id}] Transcript: '{transcript}'")
            self.session.add_user_turn(transcript)

            yield {
                "type": "transcript",
                "text": transcript,
                "role": "user"
            }

            # ── Stages 2+3: LLM → TTS (concurrent) ─
            async for chunk in self._run_llm_tts(transcript, lang, tracker):
                if self.barge_in.triggered:
                    logger.info(f"[{self.session_id}] Barge-in detected, stopping audio.")
                    break
                yield chunk

        except asyncio.CancelledError:
            logger.info(f"[{self.session_id}] Pipeline cancelled.")
        except Exception as e:
            logger.error(f"[{self.session_id}] Pipeline error: {e}", exc_info=True)
            raise
        finally:
            tracker.mark("pipeline_end")
            tracker.log_summary()

    async def run_text(
        self,
        text: str,
        language: str | None = None,
    ) -> AsyncGenerator[bytes | dict, None]:
        """
        Text-only turn (skips ASR). Accepts a plain text string from the
        client and runs LLM → TTS directly.
        """
        lang = language or self.config.language
        tracker = LatencyTracker(session_id=self.session_id)
        self.barge_in.reset()

        tracker.mark("pipeline_start")

        try:
            transcript = text.strip()
            if not transcript:
                return

            logger.info(f"[{self.session_id}] Text input: '{transcript}'")
            self.session.add_user_turn(transcript)

            yield {
                "type": "transcript",
                "text": transcript,
                "role": "user"
            }

            async for chunk in self._run_llm_tts(transcript, lang, tracker):
                if self.barge_in.triggered:
                    break
                yield chunk

        except asyncio.CancelledError:
            logger.info(f"[{self.session_id}] Pipeline cancelled.")
        except Exception as e:
            logger.error(f"[{self.session_id}] Pipeline error: {e}", exc_info=True)
            raise
        finally:
            tracker.mark("pipeline_end")
            tracker.log_summary()

    # ── Stage 1: ASR ────────────────────────────

    async def _run_asr(
        self,
        audio_bytes: bytes,
        language: str,
        tracker: LatencyTracker,
    ) -> str:
        """
        Calls Sauti ASR on Modal and returns the final transcript.
        Partial results are logged for potential early-LLM-start optimisation.
        """
        tracker.mark("asr_start")
        final_text = ""

        async for result in self.asr.transcribe_stream.remote_gen.aio(
            audio_bytes, language=language
        ):
            if result["is_final"]:
                final_text = result["text"]
                tracker.mark("asr_end")
                logger.debug(
                    f"[{self.session_id}] ASR final: '{final_text}' "
                    f"(lang={result['language']}, "
                    f"conf={result['language_probability']:.2f})"
                )
            else:
                logger.debug(f"[{self.session_id}] ASR partial: '{result['text']}'")

        return final_text.strip()

    # ── Stages 2+3: LLM → TTS ───────────────────

    async def _run_llm_tts(
        self,
        transcript: str,
        language: str,
        tracker: LatencyTracker,
    ) -> AsyncGenerator[bytes | dict, None]:
        """
        Streams tokens from DeepSeek V4 and pipes phrase-boundary chunks
        to Sauti TTS concurrently. TTS synthesis starts before LLM finishes.

        Yields both text_delta dicts (for streaming text on the client)
        and raw audio bytes from TTS, interleaved via a shared output queue.

        Architecture:
            LLM token stream → text_delta yielded immediately
                └─► SentenceSplitter
                        └─► phrase queue
                                └─► TTS synthesis tasks (concurrent)
                                        └─► audio bytes yielded in order
        """
        splitter = SentenceSplitter(flush_chars=self.config.tts_chunk_size)
        phrase_queue: asyncio.Queue[str | None] = asyncio.Queue()
        output_queue: asyncio.Queue[bytes | dict | None] = asyncio.Queue()
        error_queue: asyncio.Queue[Exception] = asyncio.Queue()

        # Task A: Stream LLM tokens → text deltas + phrases
        llm_task = asyncio.create_task(
            self._stream_llm_to_output(
                transcript, splitter, phrase_queue, output_queue, error_queue, tracker
            )
        )

        # Task B: Consume phrases → TTS → audio into output_queue
        tts_task = asyncio.create_task(
            self._stream_tts_to_output(
                phrase_queue, output_queue, error_queue, language, tracker
            )
        )

        # Drain output_queue — yields text deltas and audio interleaved
        sentinels_seen = 0
        stream_error: Exception | None = None
        try:
            while sentinels_seen < 2:
                try:
                    item = await asyncio.wait_for(
                        output_queue.get(),
                        timeout=self.config.stream_timeout_s,
                    )
                except asyncio.TimeoutError:
                    stream_error = TimeoutError(
                        f"[{self.session_id}] Output stream timed out."
                    )
                    logger.warning(str(stream_error))
                    break

                if item is None:
                    sentinels_seen += 1
                    continue

                if self.barge_in.triggered:
                    break

                yield item

        finally:
            llm_task.cancel()
            tts_task.cancel()
            await asyncio.gather(llm_task, tts_task, return_exceptions=True)

        if stream_error is None and not error_queue.empty():
            stream_error = await error_queue.get()
        if stream_error is not None:
            raise stream_error

        # Persist assistant turn in session history
        full_response = splitter.full_text()
        self.session.add_assistant_turn(full_response)
        self.context.add_assistant_message(full_response)

        yield {
            "type": "llm_response",
            "text": full_response,
            "role": "assistant"
        }

    async def _stream_llm_to_output(
        self,
        transcript: str,
        splitter: SentenceSplitter,
        phrase_queue: asyncio.Queue,
        output_queue: asyncio.Queue,
        error_queue: asyncio.Queue,
        tracker: LatencyTracker,
    ) -> None:
        """
        Streams DeepSeek V4 tokens. Each token is pushed to output_queue as a
        text_delta dict immediately AND fed to the SentenceSplitter for phrase
        extraction into phrase_queue.
        """
        import httpx

        messages = self.context.build_messages(user_message=transcript)
        tracker.mark("llm_start")
        first_token = True

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST",
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {_get_deepseek_api_key()}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.config.deepseek_model,
                        "messages": messages,
                        "stream": True,
                        "max_tokens": 128,
                        "temperature": 0.2,
                        "thinking": {"type": "disabled"},
                    },
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if self.barge_in.triggered:
                            break
                        if not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data == "[DONE]":
                            break

                        import json
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if not delta:
                            continue

                        if first_token:
                            tracker.mark("llm_first_token")
                            first_token = False

                        # Stream text delta to client immediately
                        await output_queue.put({
                            "type": "text_delta",
                            "text": delta,
                        })

                        # Feed token to splitter; get back any ready phrases
                        for phrase in splitter.feed(delta):
                            await phrase_queue.put(phrase)

            # Flush any remaining text
            for phrase in splitter.flush():
                await phrase_queue.put(phrase)

            tracker.mark("llm_end")

        except Exception as e:
            logger.error(f"[{self.session_id}] LLM stream error: {e}", exc_info=True)
            await error_queue.put(RuntimeError(f"LLM stream error: {e}"))
        finally:
            await phrase_queue.put(None)  # signal TTS consumer to finish
            await output_queue.put(None)  # signal output drain: LLM done

    async def _stream_tts_to_output(
        self,
        phrase_queue: asyncio.Queue,
        output_queue: asyncio.Queue,
        error_queue: asyncio.Queue,
        language: str,
        tracker: LatencyTracker,
    ) -> None:
        """
        Streams TTS audio continuously as phrases arrive from the LLM.

        Each phrase starts synthesis immediately upon arrival. Audio is
        forwarded in strict phrase order, but phrases synthesize concurrently
        — phrase 2 starts while phrase 1 is still producing audio.
        """
        first_audio = True
        first_audio_lock = asyncio.Lock()
        all_tasks: list[asyncio.Task] = []
        # Ordered list of per-phrase queues for draining in sequence
        phrase_queues: list[asyncio.Queue[bytes | None]] = []

        async def _synth_worker(
            phrase: str,
            out_queue: asyncio.Queue[bytes | None],
        ) -> None:
            try:
                async for audio_chunk in self.tts.synthesise_stream.remote_gen.aio(
                    phrase, language=language
                ):
                    if self.barge_in.triggered:
                        return
                    await out_queue.put(audio_chunk)
            except Exception as exc:
                logger.error(
                    f"[{self.session_id}] TTS phrase error: {exc}", exc_info=True
                )
                await error_queue.put(RuntimeError(f"TTS stream error: {exc}"))
            finally:
                await out_queue.put(None)

        # ── Dispatch + drain concurrently ──────────
        # As each phrase arrives, start its TTS immediately.
        # Meanwhile, drain completed phrase audio in order.

        drain_task = asyncio.current_task()

        async def _dispatcher():
            """Read phrases and start TTS workers as they arrive."""
            while True:
                phrase = await phrase_queue.get()
                if phrase is None or self.barge_in.triggered:
                    break
                if not phrase.strip():
                    continue

                logger.debug(f"[{self.session_id}] TTS phrase: '{phrase}'")
                pq: asyncio.Queue[bytes | None] = asyncio.Queue()
                phrase_queues.append(pq)
                task = asyncio.create_task(_synth_worker(phrase, pq))
                all_tasks.append(task)

        async def _drainer():
            """Drain per-phrase queues in order, forwarding audio to output."""
            nonlocal first_audio
            idx = 0
            while True:
                # Wait for the next phrase queue to appear
                while idx >= len(phrase_queues):
                    if not any(not t.done() for t in all_tasks) and idx >= len(phrase_queues):
                        return
                    await asyncio.sleep(0.01)

                pq = phrase_queues[idx]
                while True:
                    chunk = await pq.get()
                    if chunk is None:
                        break
                    if self.barge_in.triggered:
                        return
                    async with first_audio_lock:
                        if first_audio:
                            tracker.mark("first_audio_byte")
                            first_audio = False
                    await output_queue.put(chunk)
                idx += 1

        dispatch_task = asyncio.create_task(_dispatcher())
        drain_coro = _drainer()

        try:
            await asyncio.gather(dispatch_task, drain_coro)
        except asyncio.CancelledError:
            pass
        finally:
            dispatch_task.cancel()
            await asyncio.gather(*all_tasks, return_exceptions=True)
            await output_queue.put(None)  # signal output drain: TTS done


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

def _get_deepseek_api_key() -> str:
    import os
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY not set. Attach a Modal secret (or local env var) "
            "that injects DEEPSEEK_API_KEY into the gateway/LLM runtime before calling pipeline.run()."
        )
    return key
