"""Composite provider: try the primary, fall back to the secondary on any failure."""

import logging
import time
from collections.abc import AsyncIterator

from .base import ChatMessage, LLMProvider

logger = logging.getLogger(__name__)

COOLDOWN_SECONDS = 300


class FallbackProvider(LLMProvider):
    """After the primary fails, it is skipped for COOLDOWN_SECONDS so users don't
    pay a failing round-trip on every call; it is retried automatically after."""

    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        self.primary = primary
        self.fallback = fallback
        self._primary_down_until: float = 0.0

    def _primary_available(self) -> bool:
        return time.monotonic() >= self._primary_down_until

    def _mark_primary_down(self, exc: Exception) -> None:
        self._primary_down_until = time.monotonic() + COOLDOWN_SECONDS
        logger.warning(
            "%s failed (%r); using %s for the next %ds",
            type(self.primary).__name__, exc, type(self.fallback).__name__, COOLDOWN_SECONDS,
        )

    async def chat(
        self,
        messages: list[ChatMessage],
        system: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        if self._primary_available():
            try:
                return await self.primary.chat(messages, system=system, json_mode=json_mode, temperature=temperature)
            except Exception as exc:
                self._mark_primary_down(exc)
        return await self.fallback.chat(messages, system=system, json_mode=json_mode, temperature=temperature)

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        system: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        if self._primary_available():
            started = False
            try:
                async for token in self.primary.chat_stream(messages, system=system, temperature=temperature):
                    started = True
                    yield token
                return
            except Exception as exc:
                # Mid-stream failures can't be transparently retried — the user has
                # already seen partial output — so only fall back on a clean failure.
                if started:
                    raise
                self._mark_primary_down(exc)
        async for token in self.fallback.chat_stream(messages, system=system, temperature=temperature):
            yield token

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Chat-style fallback is NOT applied to embeddings elsewhere in the app
        # (mixed embedding models break vector search); this exists only to satisfy
        # the LLMProvider interface if someone wires a FallbackProvider for embeds.
        if self._primary_available():
            try:
                return await self.primary.embed(texts)
            except Exception as exc:
                self._mark_primary_down(exc)
        return await self.fallback.embed(texts)
