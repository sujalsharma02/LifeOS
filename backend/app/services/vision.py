"""Describe an uploaded file with Gemini vision so the text-only chat pipeline
can 'see' attachments: the caption is injected into chat context and diary
transcripts as `[User shared <file>: <caption>]`.
"""

import base64
import logging

import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta"

# Besides image/*, Gemini accepts these as inline documents.
CAPTIONABLE_MIME = {"application/pdf", "text/plain", "text/csv", "text/markdown"}

CAPTION_PROMPT = (
    "This file was shared in a personal diary conversation. Describe it in 2-4 sentences: "
    "what it shows or contains, any visible text worth noting, and anything personally "
    "meaningful (people, places, events). Plain text only, no preamble."
)


def can_caption(mime_type: str) -> bool:
    return mime_type.startswith("image/") or mime_type in CAPTIONABLE_MIME


async def describe_file(data: bytes, mime_type: str) -> str:
    """Best-effort caption; returns '' when unsupported or the call fails."""
    settings = get_settings()
    if not settings.gemini_api_key or not can_caption(mime_type):
        return ""
    model = settings.gemini_fallback_model or settings.gemini_chat_model
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(data).decode()}},
                    {"text": CAPTION_PROMPT},
                ],
            }
        ],
        "generationConfig": {"temperature": 0.2},
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{GEMINI_URL}/models/{model}:generateContent",
                params={"key": settings.gemini_api_key},
                json=body,
            )
            resp.raise_for_status()
            return str(resp.json()["candidates"][0]["content"]["parts"][0]["text"]).strip()[:1000]
    except Exception:
        logger.exception("File captioning failed; attachment saved without caption.")
        return ""
