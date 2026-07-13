"""Provider abstraction (per the architecture doc): business logic depends only on
this interface, never on a specific vendor API."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant"
    content: str


class LLMProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        system: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        """Generate a chat completion and return the text."""

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        system: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Yield the reply incrementally. Providers without native streaming
        inherit this default, which yields the whole reply at once."""
        yield await self.chat(messages, system=system, temperature=temperature)

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
