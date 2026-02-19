import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.ai.conversation import (
    check_grammar,
    generate_conversation_feedback,
    generate_conversation_reply_stream,
)
from app.ai.scenarios import SCENARIOS, ScenarioConfig, ScenarioType
from app.config import settings
from app.core.gamification_config import XP_CONVERSATION
from app.models.conversation import AIConversation
from app.models.gamification import XpEventType
from app.models.user import User
from app.schemas.conversation import (
    ConversationDetailResponse,
    ConversationEndResponse,
    ConversationFeedback,
    ConversationMessage,
    ConversationStartResponse,
    ConversationSummary,
    GrammarCorrection,
    WeeklyDialogueStatus,
)
from app.services.gamification_service import award_xp

logger = logging.getLogger(__name__)

NATIVE_LANGUAGE_MAP = {
    "ru": "Russian",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "pt": "Portuguese",
    "ar": "Arabic",
}


def _get_week_start() -> datetime:
    """Get the start of the current ISO week (Monday 00:00 UTC)."""
    now = datetime.now(timezone.utc)
    monday = now.date() - timedelta(days=now.weekday())
    return datetime(monday.year, monday.month, monday.day, tzinfo=timezone.utc)


async def _count_weekly_conversations(db: AsyncSession, user_id: uuid.UUID) -> int:
    week_start = _get_week_start()
    result = await db.execute(
        select(func.count())
        .select_from(AIConversation)
        .where(
            AIConversation.user_id == user_id,
            AIConversation.started_at >= week_start,
        )
    )
    return result.scalar_one()


async def _check_rate_limit(redis: Redis, user: User) -> None:
    key = f"ai:ratelimit:conv:{user.id}"
    limit = (
        settings.AI_RATE_LIMIT_PREMIUM_PER_MINUTE
        if user.is_premium
        else settings.AI_RATE_LIMIT_PER_MINUTE
    )
    current = await redis.get(key)
    if current is not None and int(current) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
        )
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, 60)
    await pipe.execute()


def _get_scenario(scenario_type: ScenarioType) -> ScenarioConfig:
    scenario = SCENARIOS.get(scenario_type)
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown scenario: {scenario_type}",
        )
    return scenario


async def get_weekly_dialogue_status(
    db: AsyncSession,
    user: User,
) -> WeeklyDialogueStatus:
    used = await _count_weekly_conversations(db, user.id)
    return WeeklyDialogueStatus(
        used=used,
        limit=settings.AI_FREE_DIALOGUES_PER_WEEK,
        is_premium=user.is_premium,
    )


async def start_conversation(
    db: AsyncSession,
    redis: Redis,
    user: User,
    scenario_type: ScenarioType,
) -> ConversationStartResponse:
    # Check weekly limit for free users
    if not user.is_premium:
        used = await _count_weekly_conversations(db, user.id)
        if used >= settings.AI_FREE_DIALOGUES_PER_WEEK:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Weekly dialogue limit reached ({settings.AI_FREE_DIALOGUES_PER_WEEK}/week for free users).",
            )

    await _check_rate_limit(redis, user)

    scenario = _get_scenario(scenario_type)

    # Create opening message
    now = datetime.now(timezone.utc)
    opening_message = {
        "role": "assistant",
        "content": scenario.opening_message,
        "timestamp": now.isoformat(),
        "corrections": None,
        "suggestions": None,
    }

    conversation = AIConversation(
        user_id=user.id,
        scenario=scenario_type.value,
        messages=[opening_message],
        total_turns=0,
    )
    db.add(conversation)
    await db.flush()

    return ConversationStartResponse(
        conversation_id=conversation.id,
        scenario=scenario_type,
        scenario_title=scenario.title,
        ai_message=scenario.opening_message,
        suggestions=[],
    )


async def _load_conversation(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    user: User,
) -> AIConversation:
    result = await db.execute(
        select(AIConversation).where(AIConversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    if conversation.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    return conversation


async def send_message(
    db: AsyncSession,
    redis: Redis,
    user: User,
    conversation_id: uuid.UUID,
    user_message: str,
) -> tuple[list[dict], list[str], int]:
    """Process user message: rate limit, grammar check, store. Returns (corrections, suggestions, turn_number)."""
    await _check_rate_limit(redis, user)

    conversation = await _load_conversation(db, conversation_id, user)

    if conversation.ended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversation has already ended",
        )

    max_turns = (
        settings.AI_CONVERSATION_MAX_TURNS
        if user.is_premium
        else settings.FREE_CONVERSATION_MAX_TURNS
    )
    if conversation.total_turns >= max_turns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum turns ({max_turns}) reached. Please end the conversation.",
        )

    messages = conversation.messages or []

    # Get last AI message for grammar check context
    last_ai_message = ""
    for msg in reversed(messages):
        if msg["role"] == "assistant":
            last_ai_message = msg["content"]
            break

    # Grammar check
    native_lang = NATIVE_LANGUAGE_MAP.get(user.native_language, user.native_language)
    corrections, suggestions = await check_grammar(
        user_message=user_message,
        last_ai_message=last_ai_message,
        level=user.language_level.value,
        native_language=native_lang,
    )

    # Store user message
    now = datetime.now(timezone.utc)
    user_msg_record = {
        "role": "user",
        "content": user_message,
        "timestamp": now.isoformat(),
        "corrections": corrections,
        "suggestions": suggestions,
    }
    messages.append(user_msg_record)
    conversation.messages = messages
    conversation.total_turns += 1
    flag_modified(conversation, "messages")
    await db.flush()

    return corrections, suggestions, conversation.total_turns


async def generate_ai_reply_stream(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    user: User,
) -> AsyncIterator[str]:
    """Stream AI reply and store completed message in DB."""
    conversation = await _load_conversation(db, conversation_id, user)
    messages = conversation.messages or []

    scenario_type = ScenarioType(conversation.scenario)
    scenario = _get_scenario(scenario_type)

    full_reply_parts: list[str] = []

    async for chunk in generate_conversation_reply_stream(
        scenario=scenario,
        messages=messages,
        level=user.language_level.value,
    ):
        full_reply_parts.append(chunk)
        yield chunk

    # Store completed AI message
    full_reply = "".join(full_reply_parts)
    now = datetime.now(timezone.utc)
    ai_msg_record = {
        "role": "assistant",
        "content": full_reply,
        "timestamp": now.isoformat(),
        "corrections": None,
        "suggestions": None,
    }
    messages.append(ai_msg_record)
    conversation.messages = messages
    flag_modified(conversation, "messages")
    await db.flush()


async def end_conversation(
    db: AsyncSession,
    user: User,
    conversation_id: uuid.UUID,
) -> ConversationEndResponse:
    conversation = await _load_conversation(db, conversation_id, user)

    if conversation.ended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversation has already ended",
        )

    messages = conversation.messages or []
    native_lang = NATIVE_LANGUAGE_MAP.get(user.native_language, user.native_language)

    # Generate feedback via LLM
    feedback_data = await generate_conversation_feedback(
        messages=messages,
        level=user.language_level.value,
        native_language=native_lang,
    )

    # Award XP
    xp_result = await award_xp(db, user, XP_CONVERSATION, XpEventType.conversation)

    # Update conversation
    conversation.ended_at = datetime.now(timezone.utc)
    feedback_data["total_turns"] = conversation.total_turns
    feedback_data["xp_earned"] = XP_CONVERSATION
    conversation.feedback = feedback_data
    flag_modified(conversation, "feedback")
    await db.flush()

    return ConversationEndResponse(
        conversation_id=conversation.id,
        feedback=ConversationFeedback(
            total_turns=conversation.total_turns,
            total_errors=feedback_data.get("total_errors", 0),
            common_error_types=feedback_data.get("common_error_types", []),
            strengths=feedback_data.get("strengths", []),
            areas_to_improve=feedback_data.get("areas_to_improve", []),
            overall_assessment=feedback_data.get("overall_assessment", ""),
            xp_earned=XP_CONVERSATION,
        ),
    )


async def list_conversations(
    db: AsyncSession,
    user: User,
    skip: int = 0,
    limit: int = 20,
) -> list[ConversationSummary]:
    result = await db.execute(
        select(AIConversation)
        .where(AIConversation.user_id == user.id)
        .order_by(AIConversation.started_at.desc())
        .offset(skip)
        .limit(limit)
    )
    conversations = result.scalars().all()

    summaries = []
    for conv in conversations:
        scenario_type = conv.scenario
        scenario_config = SCENARIOS.get(ScenarioType(scenario_type))
        title = scenario_config.title if scenario_config else scenario_type

        summaries.append(ConversationSummary(
            id=conv.id,
            scenario=conv.scenario,
            scenario_title=title,
            started_at=conv.started_at,
            ended_at=conv.ended_at,
            total_turns=conv.total_turns,
            is_active=conv.ended_at is None,
        ))
    return summaries


async def get_conversation(
    db: AsyncSession,
    user: User,
    conversation_id: uuid.UUID,
) -> ConversationDetailResponse:
    conversation = await _load_conversation(db, conversation_id, user)

    scenario_config = SCENARIOS.get(ScenarioType(conversation.scenario))
    title = scenario_config.title if scenario_config else conversation.scenario

    raw_messages = conversation.messages or []
    messages = []
    for msg in raw_messages:
        corrections = None
        if msg.get("corrections"):
            corrections = [
                GrammarCorrection(**c) for c in msg["corrections"]
            ]
        messages.append(ConversationMessage(
            role=msg["role"],
            content=msg["content"],
            timestamp=msg["timestamp"],
            corrections=corrections,
            suggestions=msg.get("suggestions"),
        ))

    feedback = None
    if conversation.feedback:
        fd = conversation.feedback
        feedback = ConversationFeedback(
            total_turns=fd.get("total_turns", conversation.total_turns),
            total_errors=fd.get("total_errors", 0),
            common_error_types=fd.get("common_error_types", []),
            strengths=fd.get("strengths", []),
            areas_to_improve=fd.get("areas_to_improve", []),
            overall_assessment=fd.get("overall_assessment", ""),
            xp_earned=fd.get("xp_earned", 0),
        )

    return ConversationDetailResponse(
        id=conversation.id,
        scenario=conversation.scenario,
        scenario_title=title,
        started_at=conversation.started_at,
        ended_at=conversation.ended_at,
        total_turns=conversation.total_turns,
        messages=messages,
        feedback=feedback,
    )
