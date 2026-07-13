"""Background pipeline that runs when a conversation ends:
Conversation -> Memory Extraction -> Diary Generation -> Embeddings -> Profile Update.
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session_factory
from ..llm.base import ChatMessage
from ..llm.registry import get_chat_provider, get_embedding_provider
from ..models import Conversation, Diary, DiaryMetadata, User, UserProfile
from .prompts import DIARY_GENERATION, DIARY_STYLES, MEMORY_EXTRACTION, PROFILE_UPDATE
from .util import parse_llm_json

logger = logging.getLogger(__name__)


def _transcript(conversation: Conversation) -> str:
    return "\n".join(f"{'User' if m.role == 'user' else 'Assistant'}: {m.content}" for m in conversation.messages)


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
            select(Conversation).where(Conversation.id == conversation_id)
        )
    ).scalar_one()
    await db.refresh(conv, ["messages"])
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

    # 3. Embedding over the retrieval document (summary + facts + metadata text)
    summary = str(memory.get("summary") or "")
    facts = _str_list(memory.get("important_facts"))
    topics = _str_list(memory.get("topics"))
    retrieval_doc = "\n".join(filter(None, [summary, "; ".join(facts), "; ".join(topics)])) or essay[:2000]
    try:
        embedding = (await get_embedding_provider().embed([retrieval_doc]))[0]
    except Exception:
        logger.exception("Embedding failed; diary saved without vector.")
        embedding = None

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

    # 4. Living profile update
    try:
        await _update_profile(db, user, memory)
    except Exception:
        logger.exception("Profile update failed; continuing.")

    conv.status = "completed"
    await db.commit()
    logger.info("Diary %s generated for conversation %s", diary.id, conv.id)


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
