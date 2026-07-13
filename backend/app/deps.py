import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import db as db_module
from .config import get_settings
from .db import get_db
from .models import User


async def require_db(session: AsyncSession = Depends(get_db)) -> AsyncSession:
    if not db_module.db_ready:
        raise HTTPException(503, "Database not configured. Set DATABASE_URL in backend/.env and restart.")
    return session


async def _default_user(session: AsyncSession) -> User:
    """Single-user mode, used when Google Sign-In is not configured."""
    user = (
        await session.execute(select(User).where(User.google_sub.is_(None)).limit(1))
    ).scalar_one_or_none()
    if user is None:
        user = User(name="Me")
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def get_current_user(request: Request, session: AsyncSession = Depends(require_db)) -> User:
    settings = get_settings()
    if not settings.google_client_id:
        return await _default_user(session)

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(auth[7:], settings.auth_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired session")

    user = await session.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(401, "User not found")
    return user
