"""NVIDIA Build API (build.nvidia.com) — OpenAI-compatible endpoints."""

import json
from collections.abc import AsyncIterator

import httpx

from ..config import get_settings
from .base import ChatMessage, LLMProvider


class NvidiaProvider(LLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.nvidia_api_key:
            raise RuntimeError("NVIDIA_API_KEY is not set.")
        self.api_key = settings.nvidia_api_key
        self.base_url = settings.nvidia_base_url.rstrip("/")
        self.chat_model = settings.nvidia_chat_model
        self.embedding_model = settings.nvidia_embedding_model
        self.timeout = settings.nvidia_timeout_seconds

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def chat(
        self,
        messages: list[ChatMessage],
        system: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        payload_messages = []
        if system:
            payload_messages.append({"role": "system", "content": system})
        payload_messages += [{"role": m.role, "content": m.content} for m in messages]

        body: dict = {
            "model": self.chat_model,
            "messages": payload_messages,
            "temperature": temperature,
            "max_tokens": 2048,
        }
        if json_mode:
            # Not all hosted models accept response_format; the prompt already demands
            # JSON, and parse_llm_json tolerates fenced output, so ask but don't rely on it.
            body["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions", headers=self._headers(), json=body
            )
            if json_mode and resp.status_code == 400:
                body.pop("response_format", None)
                resp = await client.post(
                    f"{self.base_url}/chat/completions", headers=self._headers(), json=body
                )
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        system: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        payload_messages = []
        if system:
            payload_messages.append({"role": "system", "content": system})
        payload_messages += [{"role": m.role, "content": m.content} for m in messages]

        body = {
            "model": self.chat_model,
            "messages": payload_messages,
            "temperature": temperature,
            "max_tokens": 2048,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST", f"{self.base_url}/chat/completions", headers=self._headers(), json=body
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload.strip() == "[DONE]":
                        break
                    try:
                        delta = json.loads(payload)["choices"][0]["delta"].get("content")
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    if delta:
                        yield delta

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers=self._headers(),
                json={
                    "model": self.embedding_model,
                    "input": texts,
                    "input_type": "passage",
                    "encoding_format": "float",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        return [item["embedding"] for item in data["data"]]
