import asyncio
import json
from collections.abc import AsyncIterator

import httpx

from ..config import get_settings
from .base import ChatMessage, LLMProvider

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Gemini returns transient 503 "model overloaded" / 429 fairly often; retry briefly.
RETRY_STATUSES = {429, 500, 503}
RETRY_DELAYS = (1.0, 3.0)


def _to_contents(messages: list[ChatMessage]) -> list[dict]:
    return [
        {"role": "model" if m.role == "assistant" else "user", "parts": [{"text": m.content}]}
        for m in messages
    ]


class GeminiProvider(LLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set. Copy backend/.env.example to backend/.env and fill it in.")
        self.api_key = settings.gemini_api_key
        self.chat_model = settings.gemini_chat_model
        self.embedding_model = settings.gemini_embedding_model
        self.embedding_dimensions = settings.embedding_dimensions
        self.fallback_model = settings.gemini_fallback_model

    def _chat_models(self) -> list[str]:
        """Configured model first; the lite fallback if it stays overloaded."""
        models = [self.chat_model]
        if self.fallback_model and self.fallback_model != self.chat_model:
            models.append(self.fallback_model)
        return models

    async def _post_with_retry(self, client: httpx.AsyncClient, model: str, body: dict) -> httpx.Response:
        for delay in (*RETRY_DELAYS, None):
            resp = await client.post(
                f"{BASE_URL}/models/{model}:generateContent",
                params={"key": self.api_key},
                json=body,
            )
            if resp.status_code in RETRY_STATUSES and delay is not None:
                await asyncio.sleep(delay)
                continue
            break
        return resp

    async def chat(
        self,
        messages: list[ChatMessage],
        system: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        contents = _to_contents(messages)
        body: dict = {
            "contents": contents,
            "generationConfig": {"temperature": temperature},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"

        async with httpx.AsyncClient(timeout=120) as client:
            for model in self._chat_models():
                resp = await self._post_with_retry(client, model, body)
                if resp.status_code not in RETRY_STATUSES:
                    break
            resp.raise_for_status()
            data = resp.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Unexpected Gemini response: {data}") from exc

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        system: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        body: dict = {
            "contents": _to_contents(messages),
            "generationConfig": {"temperature": temperature},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}

        models = self._chat_models()
        async with httpx.AsyncClient(timeout=120) as client:
            for m, model in enumerate(models):
                for delay in (*RETRY_DELAYS, None):
                    async with client.stream(
                        "POST",
                        f"{BASE_URL}/models/{model}:streamGenerateContent",
                        params={"key": self.api_key, "alt": "sse"},
                        json=body,
                    ) as resp:
                        if resp.status_code in RETRY_STATUSES and (delay is not None or m < len(models) - 1):
                            if delay is not None:
                                await asyncio.sleep(delay)
                                continue
                            break  # retries exhausted — move to the fallback model
                        resp.raise_for_status()
                        async for line in resp.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            try:
                                chunk = json.loads(line[6:])
                                text = chunk["candidates"][0]["content"]["parts"][0]["text"]
                            except (json.JSONDecodeError, KeyError, IndexError):
                                continue
                            if text:
                                yield text
                        return

    async def embed(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        async with httpx.AsyncClient(timeout=60) as client:
            for text in texts:
                resp = await client.post(
                    f"{BASE_URL}/models/{self.embedding_model}:embedContent",
                    params={"key": self.api_key},
                    json={
                        "content": {"parts": [{"text": text}]},
                        "outputDimensionality": self.embedding_dimensions,
                    },
                )
                resp.raise_for_status()
                results.append(resp.json()["embedding"]["values"])
        return results
