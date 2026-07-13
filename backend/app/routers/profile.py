from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_current_user, require_db
from ..models import User, UserProfile
from ..schemas import ProfileOut, StyleUpdate, UserSettingsOut
from ..services.prompts import DIARY_STYLES

router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/profile", response_model=ProfileOut | None)
async def get_profile(
    db: AsyncSession = Depends(require_db), user: User = Depends(get_current_user)
):
    return (
        await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    ).scalar_one_or_none()


@router.get("/settings", response_model=UserSettingsOut)
async def get_settings_route(user: User = Depends(get_current_user)):
    return user


@router.get("/styles")
async def list_styles():
    return [{"key": k, "description": v} for k, v in DIARY_STYLES.items()]


@router.patch("/settings/style", response_model=UserSettingsOut)
async def update_style(
    body: StyleUpdate,
    db: AsyncSession = Depends(require_db),
    user: User = Depends(get_current_user),
):
    if body.diary_style is not None and body.diary_style in DIARY_STYLES:
        user.diary_style = body.diary_style
    # Empty string clears the custom prompt; null leaves it untouched.
    if body.custom_style_prompt is not None:
        user.custom_style_prompt = body.custom_style_prompt.strip() or None
    await db.commit()
    await db.refresh(user)
    return user
