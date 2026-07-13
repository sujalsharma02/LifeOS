import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import get_session_factory
from ..deps import get_current_user, require_db
from ..llm.registry import get_chat_provider
from ..models import Attachment, Conversation, Diary, Message, User, UserProfile
from ..schemas import ChatRequest, ChatResponse, ConversationOut, ConversationSummaryOut, MessageOut
from ..services.chat_service import generate_reply, prepare_context
from ..services.pipeline import process_conversation
from ..models import utcnow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


async def _active_conversation(db: AsyncSession, user: User) -> Conversation:
    conv = (
        await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user.id, Conversation.status == "active")
            .order_by(Conversation.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if conv is None:
        conv = Conversation(user_id=user.id)
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
    return conv


async def _history(db: AsyncSession, conversation_id: int) -> list[Message]:
    return list(
        (
            await db.execute(
                select(Message)
                .options(selectinload(Message.attachments))
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.id)
            )
        ).scalars().all()
    )


async def _claim_attachments(db: AsyncSession, user: User, ids: list[int]) -> list[Attachment]:
    """Pending uploads the user may attach: theirs, and not on a message yet."""
    if not ids:
        return []
    return list(
        (
            await db.execute(
                select(Attachment).where(
                    Attachment.id.in_(ids[:10]),
                    Attachment.user_id == user.id,
                    Attachment.message_id.is_(None),
                )
            )
        ).scalars().all()
    )


@router.get("/conversations/active", response_model=ConversationOut)
async def get_active_conversation(
    db: AsyncSession = Depends(require_db), user: User = Depends(get_current_user)
):
    return await _active_conversation(db, user)


@router.get("/conversations", response_model=list[ConversationSummaryOut])
async def list_conversations(
    db: AsyncSession = Depends(require_db), user: User = Depends(get_current_user)
):
    """Chat history, newest first. Empty conversations are omitted; the title
    comes from the diary entry the conversation produced (null until then)."""
    msg_count = func.count(Message.id)
    stmt = (
        select(Conversation, Diary.id, Diary.title, msg_count)
        .outerjoin(Diary, Diary.conversation_id == Conversation.id)
        .join(Message, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == user.id)
        .group_by(Conversation.id, Diary.id, Diary.title)
        .order_by(Conversation.id.desc())
        .limit(100)
    )
    rows = (await db.execute(stmt)).all()
    return [
        ConversationSummaryOut(
            id=conv.id,
            status=conv.status,
            started_at=conv.started_at,
            ended_at=conv.ended_at,
            title=title,
            diary_id=diary_id,
            message_count=count,
        )
        for conv, diary_id, title, count in rows
    ]


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conversation_id: int,
    db: AsyncSession = Depends(require_db),
    user: User = Depends(get_current_user),
):
    conv = await db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(404, "Conversation not found")
    return await _history(db, conversation_id)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(require_db),
    user: User = Depends(get_current_user),
):
    text = body.message.strip()
    attachments = await _claim_attachments(db, user, body.attachment_ids)
    if not text and not attachments:
        raise HTTPException(422, "Message is empty")

    conv = await _active_conversation(db, user)
    history = await _history(db, conv.id)
    profile = (
        await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    ).scalar_one_or_none()

    reply = await generate_reply(db, user.id, history, text, profile, attachments)

    user_msg = Message(conversation_id=conv.id, role="user", content=text)
    db.add(user_msg)
    await db.flush()
    for att in attachments:
        att.message_id = user_msg.id
    db.add(Message(conversation_id=conv.id, role="assistant", content=reply))
    await db.commit()
    return ChatResponse(conversation_id=conv.id, reply=reply)


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    db: AsyncSession = Depends(require_db),
    user: User = Depends(get_current_user),
):
    """Server-sent events: `{"token": ...}` chunks, then `{"done": true}`.

    Context prep (RAG decision + retrieval) runs before the stream opens; the
    messages are persisted with a fresh session once the reply is complete.
    """
    text = body.message.strip()
    attachments = await _claim_attachments(db, user, body.attachment_ids)
    if not text and not attachments:
        raise HTTPException(422, "Message is empty")

    conv = await _active_conversation(db, user)
    history = await _history(db, conv.id)
    profile = (
        await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    ).scalar_one_or_none()
    system, messages = await prepare_context(db, user.id, history, text, profile, attachments)
    conv_id = conv.id
    attachment_ids = [a.id for a in attachments]

    async def events():
        parts: list[str] = []
        try:
            async for token in get_chat_provider().chat_stream(messages, system=system, temperature=0.8):
                parts.append(token)
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception:
            logger.exception("Streaming reply failed for conversation %s", conv_id)
            yield f"data: {json.dumps({'error': 'The companion had trouble replying — please try again.'})}\n\n"
            return
        reply = "".join(parts).strip()
        if reply:
            # The request-scoped session may already be torn down; use a fresh one.
            async with get_session_factory()() as session:
                user_msg = Message(conversation_id=conv_id, role="user", content=text)
                session.add(user_msg)
                await session.flush()
                if attachment_ids:
                    await session.execute(
                        update(Attachment)
                        .where(Attachment.id.in_(attachment_ids))
                        .values(message_id=user_msg.id)
                    )
                session.add(Message(conversation_id=conv_id, role="assistant", content=reply))
                await session.commit()
        yield f"data: {json.dumps({'done': True, 'conversation_id': conv_id})}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/conversations/{conversation_id}/end", response_model=ConversationOut)
async def end_conversation(
    conversation_id: int,
    background: BackgroundTasks,
    db: AsyncSession = Depends(require_db),
    user: User = Depends(get_current_user),
):
    conv = await db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(404, "Conversation not found")
    if conv.status != "active":
        return conv

    conv.status = "processing"
    conv.ended_at = utcnow()
    await db.commit()
    await db.refresh(conv)

    background.add_task(process_conversation, conv.id)
    return conv


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(require_db),
    user: User = Depends(get_current_user),
):
    conv = await db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(404, "Conversation not found")
    diary_id = (
        await db.execute(select(Diary.id).where(Diary.conversation_id == conv.id).limit(1))
    ).scalar_one_or_none()
    out = ConversationOut.model_validate(conv)
    out.diary_id = diary_id
    return out
