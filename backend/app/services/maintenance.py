"""Nightly maintenance (the "memory manager"):

1. Delete temporary memories past their expires_at.
2. Per user, ask the LLM to consolidate memories — merge duplicates (tracking
   progression), fix categories/importance, drop stale facts.
3. Purge Cloudinary attachments older than attachment_ttl_days.

Runs from an asyncio loop started in the app lifespan; each step degrades
independently, so one provider outage never blocks the others.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_session_factory
from ..llm.base import ChatMessage
from ..llm.registry import get_chat_provider, get_embedding_provider
from ..models import Attachment, Memory
from .pipeline import MEMORY_CATEGORIES
from .prompts import MEMORY_CONSOLIDATION
from .util import parse_llm_json

logger = logging.getLogger(__name__)

MAX_MEMORIES_PER_PASS = 200


async def run_maintenance() -> dict:
    """Run all maintenance steps; returns per-step counts for logging/manual runs."""
    report = {"expired": 0, "consolidated_users": 0, "purged_files": 0}
    async with get_session_factory()() as db:
        try:
            report["expired"] = await _expire_memories(db)
        except Exception:
            logger.exception("Memory expiry failed.")
        try:
            report["purged_files"] = await _purge_attachments(db)
        except Exception:
            logger.exception("Attachment purge failed.")
        try:
            report["consolidated_users"] = await _consolidate_all(db)
        except Exception:
            logger.exception("Memory consolidation failed.")
    logger.info("Maintenance done: %s", report)
    return report


async def _expire_memories(db: AsyncSession) -> int:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        delete(Memory).where(Memory.expires_at.is_not(None), Memory.expires_at < now)
    )
    await db.commit()
    return result.rowcount or 0


async def _purge_attachments(db: AsyncSession) -> int:
    from . import cloudstore

    if not cloudstore.is_configured():
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=get_settings().attachment_ttl_days)
    rows = (
        await db.execute(
            select(Attachment).where(Attachment.deleted.is_(False), Attachment.created_at < cutoff)
        )
    ).scalars().all()
    purged = 0
    for att in rows:
        try:
            await cloudstore.destroy(att.public_id, att.resource_type)
            att.deleted = True
            purged += 1
        except Exception:
            logger.exception("Failed to purge attachment %s from Cloudinary.", att.id)
    await db.commit()
    return purged


async def _consolidate_all(db: AsyncSession) -> int:
    user_ids = (await db.execute(select(Memory.user_id).distinct())).scalars().all()
    done = 0
    for user_id in user_ids:
        try:
            await _consolidate_user(db, user_id)
            done += 1
        except Exception:
            logger.exception("Consolidation failed for user %s.", user_id)
    return done


async def _consolidate_user(db: AsyncSession, user_id: int) -> None:
    memories = (
        await db.execute(
            select(Memory)
            .where(Memory.user_id == user_id)
            .order_by(Memory.created_at)
            .limit(MAX_MEMORIES_PER_PASS)
        )
    ).scalars().all()
    if len(memories) < 2:
        return

    payload = json.dumps(
        [
            {
                "id": m.id,
                "text": m.text,
                "category": m.category,
                "importance": m.importance,
                "created": str(m.created_at.date()),
                "times_retrieved": m.times_retrieved,
            }
            for m in memories
        ],
        ensure_ascii=False,
    )
    raw = await get_chat_provider().chat(
        [ChatMessage(role="user", content=MEMORY_CONSOLIDATION.format(memories=payload))],
        json_mode=True,
        temperature=0.1,
    )
    actions = parse_llm_json(raw).get("actions")
    if not isinstance(actions, list):
        return

    settings = get_settings()
    by_id = {m.id: m for m in memories}
    updated: list[Memory] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        try:
            mem = by_id.get(int(action.get("id")))
        except (TypeError, ValueError):
            continue
        if mem is None:  # never touch ids outside this user's set
            continue
        op = action.get("op")
        if op == "delete":
            await db.delete(mem)
        elif op == "update":
            text = str(action.get("text") or "").strip()[:500]
            if text:
                mem.text = text
            category = str(action.get("category") or mem.category)
            if category in MEMORY_CATEGORIES and category != mem.category:
                mem.category = category
                mem.expires_at = (
                    datetime.now(timezone.utc) + timedelta(days=settings.temporary_memory_days)
                    if category == "temporary"
                    else None
                )
            try:
                mem.importance = min(max(float(action.get("importance") or mem.importance), 0.0), 1.0)
            except (TypeError, ValueError):
                pass
            updated.append(mem)

    # Keep vectors in sync with the rewritten text / importance.
    to_embed = [m for m in updated if m.importance >= settings.memory_embed_min_importance]
    for m in updated:
        if m.importance < settings.memory_embed_min_importance:
            m.embedding = None
    if to_embed:
        try:
            vectors = await get_embedding_provider().embed([m.text for m in to_embed])
            for m, vec in zip(to_embed, vectors):
                m.embedding = vec
        except Exception:
            logger.exception("Re-embedding consolidated memories failed for user %s.", user_id)
    await db.commit()


async def maintenance_loop(interval_hours: int = 24, initial_delay_seconds: int = 120) -> None:
    """Started in the app lifespan. The initial delay also makes the job run shortly
    after every cold start — on hosts that sleep the process (Render free tier),
    that is what actually keeps maintenance 'nightly'."""
    await asyncio.sleep(initial_delay_seconds)
    while True:
        try:
            await run_maintenance()
        except Exception:
            logger.exception("Maintenance run crashed; will retry next interval.")
        await asyncio.sleep(interval_hours * 3600)
