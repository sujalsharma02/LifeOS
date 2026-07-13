import logging
from functools import lru_cache

from ..config import get_settings
from .base import LLMProvider
from .fallback import FallbackProvider

logger = logging.getLogger(__name__)


@lru_cache
def get_chat_provider() -> LLMProvider:
    """Primary chat provider, wrapped with the configured fallback.

    If the primary can't even be constructed (e.g. missing API key), the fallback
    is used directly.
    """
    settings = get_settings()
    fallback_name = settings.llm_fallback_provider.lower()

    try:
        primary = _build(settings.llm_provider)
    except Exception as exc:
        if fallback_name and fallback_name != settings.llm_provider.lower():
            logger.warning(
                "Primary provider '%s' unavailable (%s); using '%s'.",
                settings.llm_provider, exc, fallback_name,
            )
            return _build(fallback_name)
        raise

    if fallback_name and fallback_name != settings.llm_provider.lower():
        try:
            return FallbackProvider(primary, _build(fallback_name))
        except Exception as exc:
            logger.warning("Fallback provider '%s' unavailable (%s); running without fallback.", fallback_name, exc)
    return primary


@lru_cache
def get_embedding_provider() -> LLMProvider:
    """Embeddings intentionally have NO fallback: mixing embedding models in one
    vector space silently breaks similarity search."""
    settings = get_settings()
    name = settings.embedding_provider or settings.llm_provider
    return _build(name)


def _build(name: str) -> LLMProvider:
    name = name.lower()
    if name == "gemini":
        from .gemini import GeminiProvider

        return GeminiProvider()
    if name == "nvidia":
        from .nvidia import NvidiaProvider

        return NvidiaProvider()
    if name == "voyage":
        from .voyage import VoyageProvider

        return VoyageProvider()
    raise ValueError(f"Unknown LLM provider: {name}")
