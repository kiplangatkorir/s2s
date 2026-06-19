"""
Quick WebSocket client for a live S2S turn through the local gateway.

Usage:
    # 1. Make sure the gateway is running (separate terminal):
    #      set DEEPSEEK_API_KEY=sk-...
    #      uvicorn gateway.ws_server:app --host 0.0.0.0 --port 8000
    #
    # 2. Run this script with a WAV file of you speaking Swahili:
    #      python scripts/ws_client.py path/to/audio.wav
    #
    #    Or generate a 2-second silence test tone (no mic needed):
    #      python scripts/ws_client.py --silence
    #
    # The script sends the audio as binary frames, then an end_turn signal,
    # and prints every response (binary audio chunks + JSON events).
"""

from __future__ import annotations

import asyncio
import sys
import time
import wave
from pathlib import Path

import numpy as np

try:
    import websockets
except ImportError:
    print("Install websockets first:  pip install websockets")
    sys.exit(1)

GATEWAY_URL = "ws://localhost:8000/ws"
SILENCE_SAMPLE_RATE = 16_000
SILENCE_SECONDS = 2.0


def load_wav_pcm16(path: str) -> bytes:
    """Read a WAV file and return raw int16 PCM bytes (mono, 16 kHz preferred)."""
    with wave.open(path, "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())

    if sample_width != 2:
        print(f"[warn] WAV sample_width={sample_width}, expected 2 (int16). Proceeding anyway.")
    if channels != 1:
        print(f"[warn] WAV has {channels} channels, converting to mono.")
        audio = np.frombuffer(raw, dtype=np.int16).reshape(-1, channels).mean(axis=1).astype(np.int16)
        raw = audio.tobytes()
    if sample_rate != 16_000:
        print(f"[warn] WAV sample_rate={sample_rate}, expected 16000. ASR may still handle it.")
    print(f"[info] Loaded {path}: {len(raw) / (2 * 16_000):.2f}s of int16 PCM")
    return raw


def generate_silence() -> bytes:
    """Generate a short silence (low-amplitude noise) as int16 PCM at 16 kHz."""
    n_samples = int(SILENCE_SAMPLE_RATE * SILENCE_SECONDS)
    # Very low noise so ASR doesn't reject it as pure silence
    audio = (np.random.randn(n_samples) * 50).astype(np.int16)
    raw = audio.tobytes()
    print(f"[info] Generated {SILENCE_SECONDS}s of near-silence ({len(raw)} bytes)")
    return raw


async def run_turn(audio_bytes: bytes, url: str = GATEWAY_URL) -> None:
    """Send audio + end_turn over WebSocket and print all responses."""
    print(f"[info] Connecting to {url}")
    t0 = time.perf_counter()

    async with websockets.connect(url) as ws:
        # --- Send audio in ~4 KB binary frames ---
        chunk_size = 4096
        for i in range(0, len(audio_bytes), chunk_size):
            await ws.send(audio_bytes[i : i + chunk_size])
        print(f"[info] Sent {len(audio_bytes)} bytes of audio in {(time.perf_counter()-t0)*1000:.0f}ms")

        # --- Signal end of turn ---
        await ws.send('{"type": "end_turn"}')
        print("[info] Sent end_turn, waiting for response...")
        print("-" * 50)

        audio_chunks: list[bytes] = []
        first_audio = True

        async for message in ws:
            elapsed = (time.perf_counter() - t0) * 1000

            if isinstance(message, bytes):
                if first_audio:
                    print(f"[audio] First audio chunk: {len(message)} bytes @ {elapsed:.0f}ms")
                    first_audio = False
                else:
                    print(f"[audio] Chunk: {len(message)} bytes @ {elapsed:.0f}ms")
                audio_chunks.append(message)
            else:
                print(f"[json]  {message}  @ {elapsed:.0f}ms")
                if '"turn_complete"' in message or '"error"' in message:
                    break

    print("-" * 50)
    total_audio = sum(len(c) for c in audio_chunks)
    duration_s = total_audio / (2 * 48_000)  # int16 @ 48 kHz (TTS default)
    print(f"[done] Received {len(audio_chunks)} audio chunks "
          f"({total_audio} bytes, ~{duration_s:.2f}s of playback)")
    print(f"[done] Total turn time: {(time.perf_counter()-t0)*1000:.0f}ms")

    # Optionally save to WAV
    if audio_chunks:
        out_path = "live_turn_output.wav"
        pcm = b"".join(audio_chunks)
        with wave.open(out_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(48_000)
            wf.writeframes(pcm)
        print(f"[done] Saved TTS response to {out_path}")


def main() -> None:
    if "--silence" in sys.argv:
        audio = generate_silence()
    elif len(sys.argv) > 1 and sys.argv[1] != "--silence":
        audio = load_wav_pcm16(sys.argv[1])
    else:
        print(__doc__)
        print("ERROR: Provide a WAV file path or --silence flag.")
        sys.exit(1)

    asyncio.run(run_turn(audio))


if __name__ == "__main__":
    main()
