from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..deps import get_current_user, require_db
from ..models import Diary, User
from ..schemas import DiaryDetailOut, DiaryOut

router = APIRouter(prefix="/api/diaries", tags=["diaries"])


@router.get("", response_model=list[DiaryOut])
async def list_diaries(
    db: AsyncSession = Depends(require_db), user: User = Depends(get_current_user)
):
    rows = (
        await db.execute(
            select(Diary).where(Diary.user_id == user.id).order_by(Diary.date.desc(), Diary.id.desc())
        )
    ).scalars().all()
    return rows


@router.get("/{diary_id}", response_model=DiaryDetailOut)
async def get_diary(
    diary_id: int, db: AsyncSession = Depends(require_db), user: User = Depends(get_current_user)
):
    diary = (
        await db.execute(
            select(Diary).options(selectinload(Diary.meta)).where(Diary.id == diary_id)
        )
    ).scalar_one_or_none()
    if diary is None or diary.user_id != user.id:
        raise HTTPException(404, "Diary not found")
    return diary
