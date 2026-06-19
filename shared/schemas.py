"""
shared/schemas.py — Pydantic models shared across the pipeline
"""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal


class AudioChunk(BaseModel):
    session_id: str
    audio_bytes: bytes          # raw PCM int16 mono
    sample_rate: int = 48_000   # TTS playback default; ASR input remains 16 kHz
    sequence: int = 0           # chunk order for reassembly
    is_final: bool = False      # True = end of user utterance


class TranscriptResult(BaseModel):
    session_id: str
    text: str
    is_final: bool
    language: str
    language_probability: float
    start: float = 0.0
    end: float = 0.0


class TTSRequest(BaseModel):
    text: str
    language: str = "sw"
    voice: str = "default"
    output_format: Literal["pcm", "opus"] = "pcm"


class PipelineEvent(BaseModel):
    """Structured event for observability / logging."""
    session_id: str
    event: str                  # e.g. "asr_start", "first_audio_byte"
    value_ms: float | None = None
    metadata: dict = Field(default_factory=dict)
