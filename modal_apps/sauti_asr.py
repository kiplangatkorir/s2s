"""Modal ASR app for the MsingiAI Sauti S2S pipeline.

This wraps the Track A Whisper/Paza checkpoint that already lives in Modal:

    volume: sauti-asr-checkpoints
    mount:  /ckpts
    model:  /ckpts/track_a_whisper_paza_full

Deploy:
    modal deploy modal_apps/sauti_asr.py
"""

from __future__ import annotations

import io
import math
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterator

import modal
import numpy as np


REMOTE_ASR_PACKAGE_PARENT = "/root/sauti_asr_pkg"


def _resolve_local_asr_package(source_file: str | Path | None = None) -> Path:
    """Resolve the sibling ASR package locally without failing inside Modal."""
    here = Path(source_file or __file__).resolve()
    if len(here.parents) > 2:
        candidate = here.parents[2] / "sauti-asr" / "sauti_asr"
        if candidate.exists():
            return candidate
    return Path(REMOTE_ASR_PACKAGE_PARENT) / "sauti_asr"


LOCAL_ASR_PACKAGE = _resolve_local_asr_package()

asr_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "libsndfile1", "libsox-fmt-all")
    .pip_install(
        "torch==2.2.0",
        "torchaudio==2.2.0",
        "transformers==4.46.3",
        "safetensors>=0.4.0",
        "soundfile>=0.12.0",
        "soxr>=0.3.0",
        "numpy<2",
        "fastapi[standard]>=0.110.0",
    )
    .env(
        {
            "HF_AUDIO_DECODER": "soundfile",
            "DATASETS_AUDIO_BACKEND": "soundfile",
            "HF_HOME": "/root/.cache/huggingface",
            "TRANSFORMERS_CACHE": "/root/.cache/huggingface/transformers",
            "PYTHONUTF8": "1",
        }
    )
    .add_local_dir(
        str(LOCAL_ASR_PACKAGE),
        remote_path=f"{REMOTE_ASR_PACKAGE_PARENT}/sauti_asr",
        copy=True,
    )
)

app = modal.App("msingiai-sauti-asr", image=asr_image)

hf_cache_volume = modal.Volume.from_name("sauti-asr-hf-cache", create_if_missing=True)
checkpoint_volume = modal.Volume.from_name("sauti-asr-checkpoints", create_if_missing=False)

CHECKPOINT_DIR = "/ckpts/track_a_whisper_paza_full"
SAMPLE_RATE = 16_000
CHUNK_SECONDS = 10.0
SILENCE_RMS_THRESHOLD = 1e-4


@app.cls(
    gpu="A10G",
    min_containers=1,
    volumes={
        "/root/.cache/huggingface": hf_cache_volume,
        "/ckpts": checkpoint_volume,
    },
    timeout=60 * 20,
)
class SautiASR:
    """Persistent GPU ASR worker backed by the Track A Whisper/Paza checkpoint."""

    checkpoint_path: str = CHECKPOINT_DIR
    chunk_seconds: float = CHUNK_SECONDS
    silence_rms_threshold: float = SILENCE_RMS_THRESHOLD

    @modal.enter()
    def load_model(self) -> None:
        _prepare_asr_package_import()
        if "torchcodec" not in sys.modules:
            sys.modules["torchcodec"] = None

        from sauti_asr.whisper_experiment import WhisperGenerationDecoder

        print(f"[SautiASR] Loading Track A checkpoint from {self.checkpoint_path}")
        self.decoder = WhisperGenerationDecoder.from_pretrained(
            checkpoint=self.checkpoint_path,
            model_id_fallback="microsoft/paza-whisper-large-v3-turbo",
            language="sw",
            task="transcribe",
            max_new_tokens=128,
            num_beams=1,
        )
        print("[SautiASR] Ready.")

    @modal.method()
    def transcribe_stream(
        self,
        audio_bytes: bytes,
        language: str = "sw",
        task: str = "transcribe",
        input_format: str = "pcm_s16le",
    ) -> Iterator[dict]:
        """Transcribe an utterance and yield chunk-level partials plus a final result.

        The gateway path uses raw 16 kHz mono int16 PCM. For smoke tests and HTTP
        calls, WAV/FLAC/MP3-like containers are also accepted when `input_format`
        is not `pcm_s16le` or the bytes have a recognizable container header.
        """
        del language, task  # Track A is configured for Swahili transcription.

        waveform, sample_rate = _decode_audio_bytes(audio_bytes, input_format)
        if waveform.size == 0:
            yield _empty_result(is_final=True)
            return

        start = time.perf_counter()
        transcript_parts: list[str] = []

        for result in self._transcribe_chunked(waveform, sample_rate):
            if not result["skipped"]:
                transcript_parts.append(result["text"])
                yield {
                    "text": result["text"],
                    "is_final": False,
                    "start": result["start"],
                    "end": result["end"],
                    "language": "sw",
                    "language_probability": 1.0,
                }

        final_text = " ".join(transcript_parts).strip()
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"[SautiASR] Transcribed in {elapsed_ms:.1f}ms: {final_text!r}")

        yield {
            "text": final_text,
            "is_final": True,
            "start": 0.0,
            "end": round(len(waveform) / float(sample_rate), 3),
            "language": "sw",
            "language_probability": 1.0,
        }

    def _transcribe_chunked(self, waveform: np.ndarray, sample_rate: int) -> Iterator[dict]:
        chunk_samples = max(1, int(self.chunk_seconds * sample_rate))
        total_samples = len(waveform)
        segment_count = max(1, math.ceil(total_samples / chunk_samples))

        for index in range(segment_count):
            start_sample = index * chunk_samples
            end_sample = min(total_samples, start_sample + chunk_samples)
            chunk = waveform[start_sample:end_sample]
            if chunk.size == 0:
                continue

            start_seconds = start_sample / float(sample_rate)
            end_seconds = end_sample / float(sample_rate)
            rms = float((chunk**2).mean() ** 0.5)
            if rms < self.silence_rms_threshold:
                text = ""
                skipped = True
            else:
                text = self.decoder.transcribe_waveform(chunk, sample_rate).strip()
                skipped = _is_empty_hypothesis(text)

            yield {
                "index": index,
                "start": round(start_seconds, 3),
                "end": round(end_seconds, 3),
                "text": text,
                "skipped": skipped,
                "rms": round(rms, 6),
            }

    @modal.method()
    def transcribe_bytes(self, audio_bytes: bytes, filename: str = "audio.wav") -> dict:
        """Compatibility method matching the existing Track A service shape."""
        waveform, sample_rate = _decode_container_bytes(audio_bytes, filename)
        segments = list(self._transcribe_chunked(waveform, sample_rate))
        text = " ".join(seg["text"] for seg in segments if not seg["skipped"]).strip()
        duration_seconds = len(waveform) / float(sample_rate) if sample_rate else 0.0
        return {
            "filename": filename,
            "checkpoint": self.checkpoint_path,
            "text": text,
            "segments": segments,
            "duration_seconds": round(duration_seconds, 3),
        }


@app.function()
@modal.fastapi_endpoint(method="POST")
async def transcribe_endpoint(item: dict) -> dict:
    """HTTP smoke endpoint.

    Body:
        {"audio_b64": "<base64 audio>", "filename": "audio.wav"}
    """
    import base64

    audio_bytes = base64.b64decode(item["audio_b64"])
    filename = item.get("filename", "audio.wav")

    asr = SautiASR()
    result = asr.transcribe_bytes.remote(audio_bytes, filename)
    return {"transcript": result["text"], "language": "sw", "checkpoint": result["checkpoint"]}


def _decode_audio_bytes(audio_bytes: bytes, input_format: str) -> tuple[np.ndarray, int]:
    if input_format == "pcm_s16le" and not _looks_like_container(audio_bytes):
        return _pcm16_to_array(audio_bytes), SAMPLE_RATE
    return _decode_container_bytes(audio_bytes, "audio.wav")


def _prepare_asr_package_import() -> None:
    """Make the mounted `sauti_asr` package win over Modal's app module name."""
    if REMOTE_ASR_PACKAGE_PARENT not in sys.path:
        sys.path.insert(0, REMOTE_ASR_PACKAGE_PARENT)

    loaded = sys.modules.get("sauti_asr")
    if loaded is not None and not hasattr(loaded, "__path__"):
        # Modal imports this app as /root/sauti_asr.py for `modal run`.
        # That module blocks `import sauti_asr.whisper_experiment`, so remove
        # the alias after the class has already been imported.
        del sys.modules["sauti_asr"]


def _decode_container_bytes(audio_bytes: bytes, filename: str) -> tuple[np.ndarray, int]:
    import torchaudio

    suffix = os.path.splitext(filename)[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(audio_bytes)
        audio_path = handle.name
    try:
        waveform, sample_rate = torchaudio.load(audio_path)
    finally:
        try:
            os.unlink(audio_path)
        except OSError:
            pass

    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    return waveform.squeeze(0).numpy().astype(np.float32), int(sample_rate)


def _pcm16_to_array(audio_bytes: bytes) -> np.ndarray:
    audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
    return audio_int16.astype(np.float32) / 32768.0


def _looks_like_container(audio_bytes: bytes) -> bool:
    return audio_bytes.startswith((b"RIFF", b"fLaC", b"OggS", b"ID3", b"\xff\xfb"))


def _is_empty_hypothesis(text: str) -> bool:
    return not text or text.strip().lower() in {"unk", "<unk>"}


def _empty_result(is_final: bool) -> dict:
    return {
        "text": "",
        "is_final": is_final,
        "start": 0.0,
        "end": 0.0,
        "language": "sw",
        "language_probability": 1.0,
    }


@app.local_entrypoint()
def main(audio_file: str = "") -> None:
    if not audio_file:
        print("Provide --audio-file path/to/audio.wav for a smoke test.")
        return
    with open(audio_file, "rb") as handle:
        audio_bytes = handle.read()
    asr = SautiASR()
    for result in asr.transcribe_stream.remote_gen(
        audio_bytes,
        input_format="container",
    ):
        status = "FINAL" if result["is_final"] else "partial"
        print(f"[{status}] {result['text']}")
