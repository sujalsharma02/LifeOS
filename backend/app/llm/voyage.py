"""Voyage AI embeddings — optional alternative embedding backend.

Chat still goes through the configured chat provider; only embed() is used here.
"""

import httpx

from ..config import get_settings
from .base import ChatMessage, LLMProvider


class VoyageProvider(LLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.voyage_api_key:
            raise RuntimeError("VOYAGE_API_KEY is not set.")
        self.api_key = settings.voyage_api_key
        self.model = settings.voyage_embedding_model
        self.embedding_dimensions = settings.embedding_dimensions

    async def chat(self, messages: list[ChatMessage], system: str | None = None,
                   json_mode: bool = False, temperature: float = 0.7) -> str:
        raise NotImplementedError("Voyage AI is embeddings-only.")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "input": texts,
                    "output_dimension": self.embedding_dimensions,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        return [item["embedding"] for item in data["data"]]
