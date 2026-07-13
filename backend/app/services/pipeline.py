"""Background pipeline that runs when a conversation ends:
Conversation -> Memory Extraction -> Diary Generation -> Embeddings -> Profile Update.
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import get_settings
from ..db import get_session_factory
from ..llm.base import ChatMessage
from ..llm.registry import get_chat_provider, get_embedding_provider
from ..models import Conversation, Diary, DiaryMetadata, Memory, Message, User, UserProfile
from .prompts import DIARY_GENERATION, DIARY_STYLES, MEMORY_EXTRACTION, PROFILE_UPDATE
from .util import parse_llm_json

logger = logging.getLogger(__name__)

MEMORY_CATEGORIES = {"permanent", "long_term", "temporary"}


def attachment_note(a) -> str:
    """How an attachment appears to the (text-only) LLM."""
    if a.caption:
        return f"[User shared {a.filename}: {a.caption}]"
    return f"[User shared a file: {a.filename}]"


def message_llm_text(m: Message) -> str:
    """Message content as the LLM should see it — attachment captions included."""
    return "\n".join([m.content, *(attachment_note(a) for a in m.attachments)]).strip()


def _transcript(conversation: Conversation) -> str:
    return "\n".join(
        f"{'User' if m.role == 'user' else 'Assistant'}: {message_llm_text(m)}"
        for m in conversation.messages
    )


def _str_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v)[:300] for v in value if v][:20]


async def process_conversation(conversation_id: int) -> None:
    """Entry point for the background job. Opens its own DB session."""
    async with get_session_factory()() as db:
        try:
            await _process(db, conversation_id)
        except Exception:
            logger.exception("Diary pipeline failed for conversation %s", conversation_id)
            conv = await db.get(Conversation, conversation_id)
            if conv:
                conv.status = "failed"
                await db.commit()


async def _process(db: AsyncSession, conversation_id: int) -> None:
    conv = (
        await db.execute(
            select(Conversation)
            .options(selectinload(Conversation.messages).selectinload(Message.attachments))
            .where(Conversation.id == conversation_id)
        )
    ).scalar_one()
    user = await db.get(User, conv.user_id)
    transcript = _transcript(conv)
    if not transcript.strip():
        conv.status = "completed"
        await db.commit()
        return

    provider = get_chat_provider()

    # 1. Memory extraction (structured metadata — for retrieval, not display)
    raw = await provider.chat(
        [ChatMessage(role="user", content=MEMORY_EXTRACTION.format(transcript=transcript))],
        json_mode=True,
        temperature=0.2,
    )
    memory = parse_llm_json(raw)

    # 2. Diary generation in the user's preferred style
    style_instruction = user.custom_style_prompt or DIARY_STYLES.get(user.diary_style, DIARY_STYLES["classic"])
    essay = await provider.chat(
        [ChatMessage(role="user", content=DIARY_GENERATION.format(
            style_instruction=style_instruction, transcript=transcript
        ))],
        temperature=0.9,
    )

    diary = Diary(
        user_id=user.id,
        conversation_id=conv.id,
        date=(conv.ended_at or datetime.now(timezone.utc)).date(),
        title=str(memory.get("title") or "Untitled day")[:300],
        essay=essay.strip(),
        mood=str(memory.get("mood") or "")[:60] or None,
    )
    db.add(diary)
    await db.flush()

    # 3. Embedding over the retrieval document (summary + facts + metadata text).
    # Low-importance days are stored but NOT embedded — the index stays clean and
    # the entry remains reachable through the diary list and its memories.
    settings = get_settings()
    summary = str(memory.get("summary") or "")
    facts = _str_list(memory.get("important_facts"))
    topics = _str_list(memory.get("topics"))
    importance = float(memory.get("importance_score") or 0.5)
    retrieval_doc = "\n".join(filter(None, [summary, "; ".join(facts), "; ".join(topics)])) or essay[:2000]
    embedding = None
    if importance >= settings.diary_embed_min_importance:
        try:
            embedding = (await get_embedding_provider().embed([retrieval_doc]))[0]
        except Exception:
            logger.exception("Embedding failed; diary saved without vector.")

    meta = DiaryMetadata(
        diary_id=diary.id,
        summary=summary,
        people=_str_list(memory.get("people")),
        places=_str_list(memory.get("places")),
        projects=_str_list(memory.get("projects")),
        goals=_str_list(memory.get("goals")),
        tasks=_str_list(memory.get("tasks")),
        companies=_str_list(memory.get("companies")),
        skills=_str_list(memory.get("skills")),
        topics=topics,
        events=_str_list(memory.get("events")),
        important_facts=facts,
        emotion=str(memory.get("emotion") or "")[:60] or None,
        importance_score=float(memory.get("importance_score") or 0.5),
        embedding=embedding,
    )
    db.add(meta)

    # 3b. Persist extracted memories. Postgres keeps every valid one; only those at or
    # above memory_embed_min_importance get vectors. Temporary memories carry an expiry.
    try:
        await _store_memories(db, user.id, diary.id, memory.get("memories"), settings)
    except Exception:
        logger.exception("Memory storage failed; continuing.")

    # 4. Living profile update
    try:
        await _update_profile(db, user, memory)
    except Exception:
        logger.exception("Profile update failed; continuing.")

    conv.status = "completed"
    await db.commit()
    logger.info("Diary %s generated for conversation %s", diary.id, conv.id)


async def _store_memories(db: AsyncSession, user_id: int, diary_id: int, items, settings) -> None:
    if not isinstance(items, list):
        return
    rows: list[Memory] = []
    for item in items[:30]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()[:500]
        if not text:
            continue
        category = str(item.get("category") or "temporary")
        if category not in MEMORY_CATEGORIES:
            category = "temporary"
        try:
            importance = min(max(float(item.get("importance") or 0.5), 0.0), 1.0)
        except (TypeError, ValueError):
            importance = 0.5
        expires_at = None
        if category == "temporary":
            expires_at = datetime.now(timezone.utc) + timedelta(days=settings.temporary_memory_days)
        rows.append(
            Memory(
                user_id=user_id,
                diary_id=diary_id,
                text=text,
                category=category,
                importance=importance,
                expires_at=expires_at,
            )
        )
    if not rows:
        return

    to_embed = [m for m in rows if m.importance >= settings.memory_embed_min_importance]
    if to_embed:
        try:
            vectors = await get_embedding_provider().embed([m.text for m in to_embed])
            for m, vec in zip(to_embed, vectors):
                m.embedding = vec
        except Exception:
            logger.exception("Memory embedding failed; memories saved without vectors.")
    db.add_all(rows)


async def _update_profile(db: AsyncSession, user: User, memory: dict) -> None:
    profile = (
        await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    ).scalar_one_or_none()
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
        await db.flush()

    current = {
        "current_goals": profile.current_goals,
        "interests": profile.interests,
        "career_status": profile.career_status,
        "relationships": profile.relationships,
        "preferences": profile.preferences,
        "challenges": profile.challenges,
    }
    raw = await get_chat_provider().chat(
        [ChatMessage(role="user", content=PROFILE_UPDATE.format(
            profile=json.dumps(current, ensure_ascii=False),
            summary=memory.get("summary") or "",
            facts=json.dumps(_str_list(memory.get("important_facts")), ensure_ascii=False),
            goals=json.dumps(_str_list(memory.get("goals")), ensure_ascii=False),
            people=json.dumps(_str_list(memory.get("people")), ensure_ascii=False),
        ))],
        json_mode=True,
        temperature=0.2,
    )
    updated = parse_llm_json(raw)
    profile.current_goals = _str_list(updated.get("current_goals"))
    profile.interests = _str_list(updated.get("interests"))
    profile.career_status = str(updated.get("career_status") or "")[:2000]
    profile.relationships = _str_list(updated.get("relationships"))
    profile.preferences = _str_list(updated.get("preferences"))
    profile.challenges = _str_list(updated.get("challenges"))
