from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    url: str
    filename: str
    mime_type: str
    resource_type: str
    deleted: bool  # purged from Cloudinary after the retention window
    created_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: str
    content: str
    created_at: datetime
    attachments: list[AttachmentOut] = []


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    started_at: datetime
    ended_at: datetime | None


class ChatRequest(BaseModel):
    message: str
    attachment_ids: list[int] = []


class ChatResponse(BaseModel):
    conversation_id: int
    reply: str


class DiaryMetadataOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    summary: str
    people: list[str]
    places: list[str]
    projects: list[str]
    goals: list[str]
    tasks: list[str]
    companies: list[str]
    skills: list[str]
    topics: list[str]
    events: list[str]
    important_facts: list[str]
    emotion: str | None
    importance_score: float


class DiaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: date
    title: str
    essay: str
    mood: str | None
    created_at: datetime


class DiaryDetailOut(DiaryOut):
    meta: DiaryMetadataOut | None = None


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    current_goals: list[str]
    interests: list[str]
    career_status: str
    relationships: list[str]
    preferences: list[str]
    challenges: list[str]
    updated_at: datetime


class NamedCount(BaseModel):
    name: str
    count: int


class TimelinePoint(BaseModel):
    date: date
    mood: str | None
    emotion: str | None
    importance: float


class InsightsOut(BaseModel):
    total_entries: int
    total_words: int
    first_entry_date: date | None
    current_streak: int
    longest_streak: int
    mood_counts: list[NamedCount]
    timeline: list[TimelinePoint]
    top_people: list[NamedCount]
    top_topics: list[NamedCount]
    top_places: list[NamedCount]
    top_projects: list[NamedCount]
    weekday_counts: list[int]  # Monday..Sunday


class SearchResultOut(BaseModel):
    id: int
    date: date
    title: str
    mood: str | None
    summary: str
    similarity: float


class OnThisDayOut(BaseModel):
    label: str
    diary: DiaryOut


class ReflectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    period_start: date
    period_end: date
    title: str
    content: str
    entry_count: int
    created_at: datetime


class StyleUpdate(BaseModel):
    diary_style: str | None = None
    custom_style_prompt: str | None = None


class UserSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    diary_style: str
    custom_style_prompt: str | None
