"""Per-user conversation state helpers."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

from shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Turn:
    role: Literal["user", "assistant"]
    text: str
    timestamp: float = field(default_factory=time.time)


class Session:
    """Lightweight in-memory store of conversation turns per session."""

    def __init__(self, session_id: str, max_turns: int = 20) -> None:
        self.session_id = session_id
        self.max_turns = max_turns
        self._turns: list[Turn] = []
        self.created_at = time.time()

    def add_user_turn(self, text: str) -> None:
        self._turns.append(Turn(role="user", text=text))
        self._trim()

    def add_assistant_turn(self, text: str) -> None:
        self._turns.append(Turn(role="assistant", text=text))
        self._trim()

    @property
    def turns(self) -> list[Turn]:
        return list(self._turns)

    def clear(self) -> None:
        self._turns.clear()

    def _trim(self) -> None:
        if len(self._turns) > self.max_turns:
            dropped = len(self._turns) - self.max_turns
            self._turns = self._turns[dropped:]
            logger.debug(f"[session {self.session_id}] Trimmed {dropped} old turns.")
