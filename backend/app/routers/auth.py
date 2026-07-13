from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..deps import get_current_user, require_db
from ..models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class GoogleLogin(BaseModel):
    credential: str  # Google ID token from the Sign in with Google button


class UserOut(BaseModel):
    name: str
    email: str | None
    picture: str | None


@router.get("/config")
async def auth_config():
    settings = get_settings()
    return {
        "enabled": bool(settings.google_client_id),
        "google_client_id": settings.google_client_id,
    }


@router.post("/google")
async def google_login(body: GoogleLogin, db: AsyncSession = Depends(require_db)):
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(400, "Google Sign-In is not configured on the server.")

    try:
        # google-auth is sync (verifies signature against Google's public certs)
        idinfo = await run_in_threadpool(
            google_id_token.verify_oauth2_token,
            body.credential,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as exc:
        raise HTTPException(401, f"Invalid Google token: {exc}")

    sub = idinfo["sub"]
    email = idinfo.get("email")
    user = (
        await db.execute(select(User).where(User.google_sub == sub))
    ).scalar_one_or_none()
    if user is None and email:
        # Same email seen before (e.g. pre-auth default user upgraded manually)
        user = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
    if user is None:
        user = User(google_sub=sub)
        db.add(user)

    user.google_sub = sub
    user.email = email
    user.name = idinfo.get("name") or (email.split("@")[0] if email else "Me")
    user.picture = idinfo.get("picture")
    await db.commit()
    await db.refresh(user)

    token = jwt.encode(
        {
            "sub": str(user.id),
            "exp": datetime.now(timezone.utc) + timedelta(days=settings.auth_token_days),
        },
        settings.auth_secret,
        algorithm="HS256",
    )
    return {
        "token": token,
        "user": UserOut(name=user.name, email=user.email, picture=user.picture),
    }


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user
