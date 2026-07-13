from datetime import date, datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .config import get_settings
from .db import Base

EMBED_DIM = get_settings().embedding_dimensions


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="Me")
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    picture: Mapped[str | None] = mapped_column(Text, nullable=True)
    diary_style: Mapped[str] = mapped_column(String(40), default="classic")
    custom_style_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    profile: Mapped["UserProfile | None"] = relationship(back_populates="user", uselist=False)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | processing | completed | failed
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", order_by="Message.id", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    attachments: Mapped[list["Attachment"]] = relationship(back_populates="message")


class Attachment(Base):
    """A file uploaded into chat (stored on Cloudinary, purged after a week)."""

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"), nullable=True, index=True)
    url: Mapped[str] = mapped_column(Text)
    public_id: Mapped[str] = mapped_column(String(255))
    resource_type: Mapped[str] = mapped_column(String(20), default="image")  # image | raw | video
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100), default="")
    caption: Mapped[str] = mapped_column(Text, default="")  # LLM-visible description
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)  # purged from Cloudinary
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    message: Mapped["Message | None"] = relationship(back_populates="attachments")


class Memory(Base):
    """A single extracted memory. Postgres is the source of truth; the embedding
    (present only above the importance threshold) is just the search index."""

    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    diary_id: Mapped[int | None] = mapped_column(ForeignKey("diaries.id"), nullable=True, index=True)
    text: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(20), default="temporary")  # permanent | long_term | temporary
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    times_retrieved: Mapped[int] = mapped_column(Integer, default=0)
    last_referenced: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Diary(Base):
    __tablename__ = "diaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id"), nullable=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    title: Mapped[str] = mapped_column(String(300))
    essay: Mapped[str] = mapped_column(Text)
    mood: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    meta: Mapped["DiaryMetadata | None"] = relationship(back_populates="diary", uselist=False)


class DiaryMetadata(Base):
    __tablename__ = "diary_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    diary_id: Mapped[int] = mapped_column(ForeignKey("diaries.id"), unique=True, index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    people: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    places: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    projects: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    goals: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    tasks: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    companies: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    skills: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    topics: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    events: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    important_facts: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    emotion: Mapped[str | None] = mapped_column(String(60), nullable=True)
    importance_score: Mapped[float] = mapped_column(Float, default=0.5)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)

    diary: Mapped["Diary"] = relationship(back_populates="meta")


class Reflection(Base):
    """AI-written weekly reflection synthesized from the week's diary entries."""

    __tablename__ = "reflections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)
    entry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserProfile(Base):
    """The 'living user profile' — continuously updated by the diary pipeline."""

    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    current_goals: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    interests: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    career_status: Mapped[str] = mapped_column(Text, default="")
    relationships: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    preferences: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    challenges: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship(back_populates="profile")
