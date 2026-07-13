import json

from sqlalchemy.ext.asyncio import AsyncSession

from ..llm.base import ChatMessage
from ..llm.registry import get_chat_provider
from ..models import Attachment, Message, UserProfile
from .pipeline import attachment_note, message_llm_text
from .prompts import COMPANION_SYSTEM, MEMORIES_BLOCK, PROFILE_BLOCK
from .rag import decide_context_need, retrieve_memories


def profile_to_text(profile: UserProfile | None) -> str:
    if profile is None:
        return ""
    data = {
        "current_goals": profile.current_goals,
        "interests": profile.interests,
        "career_status": profile.career_status,
        "relationships": profile.relationships,
        "preferences": profile.preferences,
        "challenges": profile.challenges,
    }
    data = {k: v for k, v in data.items() if v}
    return json.dumps(data, ensure_ascii=False) if data else ""


async def prepare_context(
    db: AsyncSession,
    user_id: int,
    history: list[Message],
    user_message: str,
    profile: UserProfile | None,
    attachments: list[Attachment] | None = None,
) -> tuple[str, list[ChatMessage]]:
    """Build the (system prompt, message list) for a companion reply.

    The living profile is always loaded; diary memories only when the RAG
    decision says historical context is needed. Attachments on the new message
    appear to the LLM as caption notes appended to the user text.
    """
    if attachments:
        notes = "\n".join(attachment_note(a) for a in attachments)
        user_message = f"{user_message}\n{notes}".strip()
    needs_context, query = await decide_context_need(user_message, history)
    memories: list[str] = []
    if needs_context and query:
        try:
            memories = await retrieve_memories(db, user_id, query)
        except Exception:
            memories = []  # degrade gracefully — chat must not break if retrieval fails

    profile_text = profile_to_text(profile)
    system = COMPANION_SYSTEM.format(
        profile_block=PROFILE_BLOCK.format(profile=profile_text) if profile_text else "",
        memories_block=MEMORIES_BLOCK.format(memories="\n".join(memories)) if memories else "",
    )

    messages = [ChatMessage(role=m.role, content=message_llm_text(m)) for m in history]
    messages.append(ChatMessage(role="user", content=user_message))
    return system, messages


async def generate_reply(
    db: AsyncSession,
    user_id: int,
    history: list[Message],
    user_message: str,
    profile: UserProfile | None,
    attachments: list[Attachment] | None = None,
) -> str:
    system, messages = await prepare_context(db, user_id, history, user_message, profile, attachments)
    return await get_chat_provider().chat(messages, system=system, temperature=0.8)
