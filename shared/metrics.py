"""
shared/metrics.py — latency tracking across pipeline stages
"""

from __future__ import annotations

import time
from shared.logging import get_logger

logger = get_logger(__name__)

# Key milestones we track per turn
MILESTONES = [
    "pipeline_start",
    "asr_start",
    "asr_end",
    "llm_start",
    "llm_first_token",
    "llm_end",
    "first_audio_byte",
    "pipeline_end",
]


class LatencyTracker:
    """
    Records wall-clock timestamps at named milestones and logs a
    human-readable summary at the end of each pipeline turn.

    Key metrics reported:
      ASR latency      = asr_end - asr_start
      LLM TTFT         = llm_first_token - llm_start
      LLM total        = llm_end - llm_start
      Time to audio    = first_audio_byte - pipeline_start  ← the headline number
      Total turn time  = pipeline_end - pipeline_start
    """

    def __init__(self, session_id: str = "") -> None:
        self.session_id = session_id
        self._marks: dict[str, float] = {}

    def mark(self, name: str) -> None:
        self._marks[name] = time.perf_counter()

    def elapsed_ms(self, start: str, end: str) -> float | None:
        s = self._marks.get(start)
        e = self._marks.get(end)
        if s is None or e is None:
            return None
        return (e - s) * 1000

    def log_summary(self) -> None:
        def ms(s: str, e: str) -> str:
            v = self.elapsed_ms(s, e)
            return f"{v:.0f}ms" if v is not None else "—"

        logger.info(
            f"[metrics | {self.session_id}] "
            f"ASR={ms('asr_start','asr_end')} | "
            f"LLM-TTFT={ms('llm_start','llm_first_token')} | "
            f"LLM-total={ms('llm_start','llm_end')} | "
            f"Time-to-audio={ms('pipeline_start','first_audio_byte')} | "
            f"Turn-total={ms('pipeline_start','pipeline_end')}"
        )

    def to_dict(self) -> dict:
        ttfa_ms = self.elapsed_ms("pipeline_start", "first_audio_byte")
        return {
            "session_id": self.session_id,
            "asr_ms": self.elapsed_ms("asr_start", "asr_end"),
            "llm_ttft_ms": self.elapsed_ms("llm_start", "llm_first_token"),
            "llm_total_ms": self.elapsed_ms("llm_start", "llm_end"),
            "time_to_audio_ms": ttfa_ms,
            "ttfa_ms": ttfa_ms,
            "turn_total_ms": self.elapsed_ms("pipeline_start", "pipeline_end"),
        }


# ─────────────────────────────────────────
# shared/logging.py — structured logger
# ─────────────────────────────────────────

"""
shared/logging.py
"""

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    return logger
