"""Phase 3: analytics over the diary corpus, semantic search, memories
resurfacing, and AI-written weekly reflections."""

import logging
from collections import Counter
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_current_user, require_db
from ..llm.base import ChatMessage
from ..llm.registry import get_chat_provider, get_embedding_provider
from ..models import Diary, DiaryMetadata, Reflection, User, UserProfile
from ..schemas import (
    InsightsOut,
    NamedCount,
    OnThisDayOut,
    ReflectionOut,
    SearchResultOut,
    TimelinePoint,
)
from ..services.chat_service import profile_to_text
from ..services.prompts import WEEKLY_REFLECTION
from ..services.util import parse_llm_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["insights"])

TIMELINE_POINTS = 60
TOP_N = 8


def _streaks(dates: set[date]) -> tuple[int, int]:
    """(current, longest) runs of consecutive days with at least one entry.
    The current streak survives a missing entry for today (the day isn't over)."""
    if not dates:
        return 0, 0

    ordered = sorted(dates)
    longest = run = 1
    for prev, cur in zip(ordered, ordered[1:]):
        run = run + 1 if (cur - prev).days == 1 else 1
        longest = max(longest, run)

    today = date.today()
    anchor = today if today in dates else today - timedelta(days=1)
    current = 0
    while anchor in dates:
        current += 1
        anchor -= timedelta(days=1)
    return current, longest


def _top(counter: Counter, n: int = TOP_N) -> list[NamedCount]:
    return [NamedCount(name=name, count=count) for name, count in counter.most_common(n)]


@router.get("/insights", response_model=InsightsOut)
async def get_insights(
    db: AsyncSession = Depends(require_db), user: User = Depends(get_current_user)
):
    rows = (
        await db.execute(
            select(Diary, DiaryMetadata)
            .outerjoin(DiaryMetadata, DiaryMetadata.diary_id == Diary.id)
            .where(Diary.user_id == user.id)
            .order_by(Diary.date, Diary.id)
        )
    ).all()

    dates: set[date] = set()
    total_words = 0
    moods: Counter = Counter()
    people: Counter = Counter()
    topics: Counter = Counter()
    places: Counter = Counter()
    projects: Counter = Counter()
    weekday_counts = [0] * 7
    timeline: list[TimelinePoint] = []

    for diary, meta in rows:
        dates.add(diary.date)
        total_words += len(diary.essay.split())
        weekday_counts[diary.date.weekday()] += 1
        if diary.mood:
            moods[diary.mood.lower()] += 1
        if meta:
            people.update(p for p in meta.people if p)
            topics.update(t for t in meta.topics if t)
            places.update(p for p in meta.places if p)
            projects.update(p for p in meta.projects if p)
        timeline.append(
            TimelinePoint(
                date=diary.date,
                mood=diary.mood,
                emotion=meta.emotion if meta else None,
                importance=meta.importance_score if meta else 0.5,
            )
        )

    current_streak, longest_streak = _streaks(dates)
    return InsightsOut(
        total_entries=len(rows),
        total_words=total_words,
        first_entry_date=min(dates) if dates else None,
        current_streak=current_streak,
        longest_streak=longest_streak,
        mood_counts=_top(moods),
        timeline=timeline[-TIMELINE_POINTS:],
        top_people=_top(people),
        top_topics=_top(topics),
        top_places=_top(places),
        top_projects=_top(projects),
        weekday_counts=weekday_counts,
    )


@router.get("/search", response_model=list[SearchResultOut])
async def semantic_search(
    q: str = Query(min_length=1, max_length=500),
    db: AsyncSession = Depends(require_db),
    user: User = Depends(get_current_user),
):
    """Vector search over diary memory embeddings — 'that week I felt stuck' works."""
    try:
        query_vec = (await get_embedding_provider().embed([q]))[0]
    except Exception:
        logger.exception("Search embedding failed")
        raise HTTPException(503, "Search is unavailable right now — embedding provider failed.")

    distance = DiaryMetadata.embedding.cosine_distance(query_vec)
    rows = (
        await db.execute(
            select(Diary, DiaryMetadata, distance.label("distance"))
            .join(DiaryMetadata, DiaryMetadata.diary_id == Diary.id)
            .where(Diary.user_id == user.id, DiaryMetadata.embedding.is_not(None))
            .order_by(distance)
            .limit(10)
        )
    ).all()

    return [
        SearchResultOut(
            id=diary.id,
            date=diary.date,
            title=diary.title,
            mood=diary.mood,
            summary=meta.summary or diary.essay[:280],
            similarity=round(max(0.0, 1.0 - dist), 3),
        )
        for diary, meta, dist in rows
    ]


@router.get("/onthisday", response_model=list[OnThisDayOut])
async def on_this_day(
    db: AsyncSession = Depends(require_db), user: User = Depends(get_current_user)
):
    """Resurface past entries: a week / a month / a year ago today."""
    today = date.today()
    lookups = [
        ("A week ago", today - timedelta(days=7)),
        ("A month ago", today - timedelta(days=30)),
        ("A year ago", today - timedelta(days=365)),
    ]
    results: list[OnThisDayOut] = []
    for label, target in lookups:
        diary = (
            await db.execute(
                select(Diary)
                .where(Diary.user_id == user.id, Diary.date == target)
                .order_by(Diary.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if diary:
            results.append(OnThisDayOut(label=label, diary=diary))
    return results


@router.get("/reflections", response_model=list[ReflectionOut])
async def list_reflections(
    db: AsyncSession = Depends(require_db), user: User = Depends(get_current_user)
):
    rows = (
        await db.execute(
            select(Reflection)
            .where(Reflection.user_id == user.id)
            .order_by(Reflection.period_end.desc(), Reflection.id.desc())
        )
    ).scalars().all()
    return rows


@router.post("/reflections/generate", response_model=ReflectionOut)
async def generate_reflection(
    db: AsyncSession = Depends(require_db), user: User = Depends(get_current_user)
):
    """Synthesize the last 7 days of diary entries into a weekly reflection."""
    period_end = date.today()
    period_start = period_end - timedelta(days=6)

    rows = (
        await db.execute(
            select(Diary, DiaryMetadata)
            .outerjoin(DiaryMetadata, DiaryMetadata.diary_id == Diary.id)
            .where(Diary.user_id == user.id, Diary.date >= period_start, Diary.date <= period_end)
            .order_by(Diary.date, Diary.id)
        )
    ).all()
    if not rows:
        raise HTTPException(400, "No diary entries in the last 7 days — chat about your day first.")

    digest_lines = []
    for diary, meta in rows:
        facts = "; ".join((meta.important_facts or [])[:3]) if meta else ""
        digest_lines.append(
            f"- {diary.date} (mood: {diary.mood or 'n/a'}): "
            f"{(meta.summary if meta else '') or diary.essay[:300]}"
            + (f" | Notable: {facts}" if facts else "")
        )

    profile = (
        await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    ).scalar_one_or_none()

    raw = await get_chat_provider().chat(
        [
            ChatMessage(
                role="user",
                content=WEEKLY_REFLECTION.format(
                    period_start=period_start,
                    period_end=period_end,
                    digest="\n".join(digest_lines),
                    profile=profile_to_text(profile) or "(no profile yet)",
                ),
            )
        ],
        json_mode=True,
        temperature=0.7,
    )
    data = parse_llm_json(raw)
    title = str(data.get("title") or "Your week in review")[:300]
    content = str(data.get("content") or "").strip()
    if not content:
        raise HTTPException(502, "The model returned an empty reflection — try again.")

    # Regenerating within the same week replaces the previous reflection.
    await db.execute(
        delete(Reflection).where(
            Reflection.user_id == user.id,
            Reflection.period_start == period_start,
            Reflection.period_end == period_end,
        )
    )
    reflection = Reflection(
        user_id=user.id,
        period_start=period_start,
        period_end=period_end,
        title=title,
        content=content,
        entry_count=len(rows),
    )
    db.add(reflection)
    await db.commit()
    await db.refresh(reflection)
    return reflection
