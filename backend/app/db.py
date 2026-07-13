import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
db_ready: bool = False


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is not set. Copy backend/.env.example to backend/.env and fill it in.")
        _engine = create_async_engine(settings.async_database_url, pool_pre_ping=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def get_db():
    async with get_session_factory()() as session:
        yield session


async def init_db() -> bool:
    """Create the pgvector extension and all tables. Returns True on success."""
    global db_ready
    from . import models  # noqa: F401  (register models on Base.metadata)

    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
        db_ready = True
        logger.info("Database initialized.")
    except Exception:
        db_ready = False
        logger.exception(
            "Database initialization failed. The API will start, but data endpoints "
            "will return 503 until DATABASE_URL is configured correctly."
        )
    return db_ready
