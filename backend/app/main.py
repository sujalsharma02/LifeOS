import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db as db_module
from .config import get_settings
from .db import init_db
from .routers import auth, chat, diaries, export, insights, profile

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="LifeOS — AI Diary Assistant", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(diaries.router)
app.include_router(profile.router)
app.include_router(insights.router)
app.include_router(export.router)


@app.get("/health")
async def health():
    return {"status": "ok", "database_ready": db_module.db_ready}
