import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import BackgroundTasks, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db as db_module
from .config import get_settings
from .db import init_db
from .deps import get_current_user
from .routers import auth, chat, diaries, export, insights, profile, uploads
from .services.maintenance import maintenance_loop, run_maintenance

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ready = await init_db()
    task = asyncio.create_task(maintenance_loop()) if ready else None
    yield
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


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
app.include_router(uploads.router)


@app.get("/health")
async def health():
    return {"status": "ok", "database_ready": db_module.db_ready}


@app.post("/api/maintenance/run", dependencies=[Depends(get_current_user)])
async def trigger_maintenance(background: BackgroundTasks):
    """Manual trigger for the nightly job (also handy for external cron pings)."""
    background.add_task(run_maintenance)
    return {"status": "scheduled"}
