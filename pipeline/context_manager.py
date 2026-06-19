"""
pipeline/session.py + pipeline/context_manager.py
Combined for brevity — split into separate files if they grow large.
"""

from __future__ import annotations

from shared.logging import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────
# Session — per-user turn history
# ─────────────────────────────────────────

from pipeline.session import Session, Turn


# ─────────────────────────────────────────
# ContextManager — builds DeepSeek message list with token budget
# ─────────────────────────────────────────

class ContextManager:
    """
    Converts session history into the messages list for the DeepSeek API.
    Enforces a token budget so the prompt never blows the context window.

    Token counting is approximate (chars / 4) — good enough for budget
    enforcement without a full tokenizer dependency.
    """

    def __init__(
        self,
        max_tokens: int = 2048,
        system_prompt: str = "",
    ) -> None:
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt
        self._messages: list[dict] = []

    def add_user_message(self, text: str) -> None:
        self._messages.append({"role": "user", "content": text})

    def add_assistant_message(self, text: str) -> None:
        self._messages.append({"role": "assistant", "content": text})

    def build_messages(self, user_message: str) -> list[dict]:
        """
        Returns the final messages list to send to DeepSeek, with:
          - system prompt always first
          - trimmed history that fits within max_tokens
          - current user message appended last
        """
        system = [{"role": "system", "content": self.system_prompt}]
        current = {"role": "user", "content": user_message}

        # Trim history from oldest to fit budget
        history = list(self._messages)
        while history and self._token_count(system + history + [current]) > self.max_tokens:
            history.pop(0)
            logger.debug("[context] Trimmed one message to fit token budget.")

        messages = system + history + [current]
        self.add_user_message(user_message)  # persist for next turn

        logger.debug(
            f"[context] Sending {len(messages)} messages "
            f"(~{self._token_count(messages)} tokens)"
        )
        return messages

    def clear(self) -> None:
        self._messages.clear()

    @staticmethod
    def _token_count(messages: list[dict]) -> int:
        """Approximate token count: total chars / 4."""
        total_chars = sum(len(m.get("content", "")) for m in messages)
        return total_chars // 4
