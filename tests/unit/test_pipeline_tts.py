import asyncio

import pytest

from pipeline.orchestrator import S2SPipeline
from shared.metrics import LatencyTracker


class _FakeRemoteGen:
    def __init__(self, started: list[str], release_first: asyncio.Event) -> None:
        self._started = started
        self._release_first = release_first

    async def aio(self, text: str, language: str):
        self._started.append(text)
        if text == "first":
            await self._release_first.wait()
        yield f"{text}-audio".encode()


class _FakeSynthesiseStream:
    def __init__(self, started: list[str], release_first: asyncio.Event) -> None:
        self.remote_gen = _FakeRemoteGen(started, release_first)


class _FakeTTS:
    def __init__(self, started: list[str], release_first: asyncio.Event) -> None:
        self.synthesise_stream = _FakeSynthesiseStream(started, release_first)


@pytest.mark.asyncio
async def test_tts_queue_starts_follow_up_phrases_concurrently() -> None:
    started: list[str] = []
    release_first = asyncio.Event()
    pipeline = S2SPipeline(session_id="tts-test")
    pipeline._tts = _FakeTTS(started, release_first)

    phrase_queue: asyncio.Queue[str | None] = asyncio.Queue()
    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    await phrase_queue.put("first")
    await phrase_queue.put("second")
    await phrase_queue.put(None)

    async def collect() -> list[bytes]:
        chunks: list[bytes] = []
        task = asyncio.create_task(
            pipeline._stream_tts_from_queue(
                phrase_queue,
                audio_queue,
                asyncio.Queue(),
                language="sw",
                tracker=LatencyTracker(session_id="tts-test"),
            )
        )
        await asyncio.sleep(0.01)
        assert started == ["first", "second"]

        release_first.set()
        while True:
            chunk = await audio_queue.get()
            if chunk is None:
                break
            chunks.append(chunk)
        await task
        return chunks

    chunks = await collect()

    assert chunks == [b"first-audio", b"second-audio"]
