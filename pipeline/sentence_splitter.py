"""
pipeline/sentence_splitter.py

Watches the LLM token stream and emits phrase-sized chunks for TTS.
The goal: start TTS as early as possible without cutting mid-word.

Flush triggers (in priority order):
  1. Hard punctuation  — . ! ?
  2. Soft punctuation  — , ; : —  (only if buffer >= flush_chars)
  3. Length threshold  — buffer >= flush_chars (word-boundary cut, hard-capped at MAX_CHARS)
"""

from __future__ import annotations

import re

# Punctuation that always triggers a flush
HARD_BOUNDARIES = re.compile(r"[.!?]+")

# Punctuation that triggers a flush only once the buffer is long enough
SOFT_BOUNDARIES = re.compile(r"[,;:\u2014]+")  # includes em-dash

# Safety valve — flush even with no punctuation after this many chars.
# Lowering this keeps the TTS queue moving and reduces long-tail first-audio delay.
MAX_CHARS = 120


class SentenceSplitter:
    """
    Feed LLM delta tokens one at a time via feed().
    Collect emitted phrases, then call flush() at end-of-stream.
    """

    def __init__(self, flush_chars: int = 50, first_flush_chars: int | None = None):
        """
        flush_chars: minimum buffer size before a soft boundary triggers a flush.
        first_flush_chars: lower threshold for the first phrase only — lets TTS start sooner.
        """
        self.flush_chars = flush_chars
        self.first_flush_chars = first_flush_chars or max(20, flush_chars // 2)
        self._first_phrase_emitted = False
        self._buffer = ""
        self._all_text: list[str] = []

    def feed(self, token: str) -> list[str]:
        """
        Accepts one token (or partial token) from the LLM stream.
        Returns a list of phrases ready for TTS (usually 0 or 1 items).
        """
        self._buffer += token
        phrases: list[str] = []

        while True:
            phrase = self._try_flush()
            if phrase is None:
                break
            phrases.append(phrase)

        return phrases

    def flush(self) -> list[str]:
        """
        Call at end-of-stream to emit any remaining buffered text.
        """
        text = self._buffer.strip()
        self._buffer = ""
        if text:
            self._all_text.append(text)
            return [text]
        return []

    def full_text(self) -> str:
        """Returns the complete generated text across all phrases."""
        return " ".join(self._all_text)

    def reset(self) -> None:
        self._buffer = ""
        self._all_text = []
        self._first_phrase_emitted = False

    # ── internal ──────────────────────────────

    def _try_flush(self) -> str | None:
        """
        Checks the buffer for a flush trigger.
        Returns the phrase to flush, or None if not yet ready.
        """
        buf = self._buffer

        # 1. Hard boundary — flush everything up to and including punctuation
        m = HARD_BOUNDARIES.search(buf)
        if m:
            phrase = buf[: m.end()].strip()
            self._buffer = buf[m.end():].lstrip()
            if phrase:
                self._all_text.append(phrase)
                self._first_phrase_emitted = True
                return phrase

        # 2. Soft boundary — only if buffer is long enough
        threshold = self.first_flush_chars if not self._first_phrase_emitted else self.flush_chars
        if len(buf) >= threshold:
            m = SOFT_BOUNDARIES.search(buf)
            if m:
                phrase = buf[: m.end()].strip()
                self._buffer = buf[m.end():].lstrip()
                if phrase:
                    self._all_text.append(phrase)
                    self._first_phrase_emitted = True
                    return phrase

        # 3. Safety valve — flush at word boundary once buffer reaches flush_chars.
        # This avoids waiting for punctuation on the first chunk, which is the
        # main source of delay for first-audio playback.
        # Also acts as hard cap: no phrase will exceed MAX_CHARS.
        if len(buf) >= threshold:
            # We want to break at the last word boundary before the end of the buffer,
            # or before MAX_CHARS if it's too long.
            search_end = min(len(buf), MAX_CHARS)
            cut = buf.rfind(" ", 0, search_end)
            if cut == -1:
                if len(buf) < MAX_CHARS:
                    return None
                cut = MAX_CHARS
            phrase = buf[:cut].strip()
            if phrase:
                self._buffer = buf[cut:].lstrip()
                self._all_text.append(phrase)
                self._first_phrase_emitted = True
                return phrase

        return None
