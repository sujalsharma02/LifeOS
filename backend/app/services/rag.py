"""Selective RAG (per the architecture doc): decide first whether history is needed,
then retrieve by vector similarity over diary memory embeddings."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..llm.base import ChatMessage
from ..llm.registry import get_chat_provider, get_embedding_provider
from ..models import Diary, DiaryMetadata, Message
from .prompts import RAG_DECISION
from .util import parse_llm_json

logger = logging.getLogger(__name__)

TOP_K = 4


async def decide_context_need(user_message: str, recent: list[Message]) -> tuple[bool, str]:
    """Ask a cheap LLM call whether historical memories are needed and what to search for."""
    recent_text = "\n".join(f"{m.role}: {m.content}" for m in recent[-6:]) or "(start of conversation)"
    prompt = RAG_DECISION.format(message=user_message, recent=recent_text)
    try:
        raw = await get_chat_provider().chat(
            [ChatMessage(role="user", content=prompt)], json_mode=True, temperature=0.0
        )
        data = parse_llm_json(raw)
        return bool(data.get("needs_context")), str(data.get("search_query") or user_message)
    except Exception:
        logger.exception("RAG decision failed; skipping retrieval.")
        return False, ""


async def retrieve_memories(db: AsyncSession, user_id: int, query: str, top_k: int = TOP_K) -> list[str]:
    """Vector search over DiaryMetadata embeddings; returns formatted memory snippets."""
    vectors = await get_embedding_provider().embed([query])
    query_vec = vectors[0]

    stmt = (
        select(Diary, DiaryMetadata)
        .join(DiaryMetadata, DiaryMetadata.diary_id == Diary.id)
        .where(Diary.user_id == user_id, DiaryMetadata.embedding.is_not(None))
        .order_by(DiaryMetadata.embedding.cosine_distance(query_vec))
        .limit(top_k)
    )
    rows = (await db.execute(stmt)).all()

    snippets = []
    for diary, meta in rows:
        facts = "; ".join(meta.important_facts[:3]) if meta.important_facts else ""
        snippet = f"[{diary.date}] {diary.title}: {meta.summary}"
        if facts:
            snippet += f" Key facts: {facts}"
        snippets.append(snippet)
    return snippets
