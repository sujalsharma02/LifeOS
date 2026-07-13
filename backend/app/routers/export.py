"""Data export - users own their data (Markdown, JSON, SQLite)."""

import io
import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..deps import get_current_user, require_db
from ..models import Diary, User

router = APIRouter(prefix="/api/export", tags=["export"])


async def _load_diaries(db: AsyncSession, user_id: int) -> list[Diary]:
    return list(
        (
            await db.execute(
                select(Diary)
                .options(selectinload(Diary.meta))
                .where(Diary.user_id == user_id)
                .order_by(Diary.date)
            )
        ).scalars()
    )


def _meta_dict(diary: Diary) -> dict:
    m = diary.meta
    if m is None:
        return {}
    return {
        "summary": m.summary,
        "people": m.people, "places": m.places, "projects": m.projects,
        "goals": m.goals, "tasks": m.tasks, "companies": m.companies,
        "skills": m.skills, "topics": m.topics, "events": m.events,
        "important_facts": m.important_facts,
        "emotion": m.emotion, "importance_score": m.importance_score,
    }


@router.get("/markdown")
async def export_markdown(
    db: AsyncSession = Depends(require_db), user: User = Depends(get_current_user)
):
    diaries = await _load_diaries(db, user.id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for d in diaries:
            body = f"# {d.title}\n\n*{d.date} - mood: {d.mood or 'n/a'}*\n\n{d.essay}\n"
            zf.writestr(f"{d.date}-{d.id}.md", body)
    return Response(
        buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=lifeos-diaries-markdown.zip"},
    )


@router.get("/json")
async def export_json(
    db: AsyncSession = Depends(require_db), user: User = Depends(get_current_user)
):
    diaries = await _load_diaries(db, user.id)
    payload = [
        {
            "id": d.id,
            "date": d.date.isoformat(),
            "title": d.title,
            "essay": d.essay,
            "mood": d.mood,
            "created_at": d.created_at.isoformat(),
            "metadata": _meta_dict(d),
        }
        for d in diaries
    ]
    return Response(
        json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=lifeos-diaries.json"},
    )


@router.get("/sqlite")
async def export_sqlite(
    db: AsyncSession = Depends(require_db), user: User = Depends(get_current_user)
):
    diaries = await _load_diaries(db, user.id)
    tmp = Path(tempfile.mkstemp(suffix=".db")[1])
    conn = sqlite3.connect(tmp)
    try:
        conn.execute(
            "CREATE TABLE diaries (id INTEGER PRIMARY KEY, date TEXT, title TEXT, essay TEXT, mood TEXT, created_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE diary_metadata (diary_id INTEGER PRIMARY KEY, metadata_json TEXT)"
        )
        for d in diaries:
            conn.execute(
                "INSERT INTO diaries VALUES (?,?,?,?,?,?)",
                (d.id, d.date.isoformat(), d.title, d.essay, d.mood, d.created_at.isoformat()),
            )
            conn.execute(
                "INSERT INTO diary_metadata VALUES (?,?)",
                (d.id, json.dumps(_meta_dict(d), ensure_ascii=False)),
            )
        conn.commit()
    finally:
        conn.close()
    return FileResponse(tmp, media_type="application/octet-stream", filename="lifeos-diaries.sqlite")
