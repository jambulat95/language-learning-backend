import json
import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_current_user, get_redis
from app.ai.scenarios import SCENARIOS
from app.database import async_session_factory, get_db
from app.models.user import User
from app.schemas.conversation import (
    ConversationDetailResponse,
    ConversationEndResponse,
    ConversationStartResponse,
    ConversationSummary,
    ScenarioListItem,
    SendMessageRequest,
    StartConversationRequest,
    WeeklyDialogueStatus,
)
from app.services import conversation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("/scenarios", response_model=list[ScenarioListItem])
async def list_scenarios():
    """List all available conversation scenarios."""
    return [
        ScenarioListItem(
            type=config.type,
            title=config.title,
            description=config.description,
            suggested_turns=config.suggested_turns,
        )
        for config in SCENARIOS.values()
    ]


@router.get("/weekly-status", response_model=WeeklyDialogueStatus)
async def get_weekly_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the user's weekly dialogue usage status."""
    return await conversation_service.get_weekly_dialogue_status(db, current_user)


@router.post("/start", response_model=ConversationStartResponse, status_code=201)
async def start_conversation(
    data: StartConversationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Start a new AI conversation with a selected scenario."""
    return await conversation_service.start_conversation(
        db, redis, current_user, data.scenario,
    )


@router.post("/{conversation_id}/send")
async def send_message(
    conversation_id: uuid.UUID,
    data: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Send a message and receive SSE stream with corrections and AI reply."""
    # Process user message (grammar check + store) within the request's DB session
    corrections, suggestions, turn_number = await conversation_service.send_message(
        db, redis, current_user, conversation_id, data.message,
    )
    # Commit user message before starting SSE stream
    await db.commit()

    async def event_generator() -> AsyncIterator[dict]:
        # Emit corrections event
        yield {
            "event": "corrections",
            "data": json.dumps({
                "corrections": corrections,
                "suggestions": suggestions,
                "turn_number": turn_number,
            }),
        }

        # Stream AI reply using its own DB session (request session closes after return)
        full_reply_parts: list[str] = []
        try:
            async with async_session_factory() as stream_db:
                try:
                    async for chunk in conversation_service.generate_ai_reply_stream(
                        stream_db, conversation_id, current_user,
                    ):
                        full_reply_parts.append(chunk)
                        yield {"event": "token", "data": chunk}

                    await stream_db.commit()
                except Exception:
                    await stream_db.rollback()
                    raise

            full_reply = "".join(full_reply_parts)
            yield {
                "event": "done",
                "data": json.dumps({"ai_message": full_reply}),
            }
        except Exception:
            logger.exception("Error during AI reply streaming")
            yield {
                "event": "error",
                "data": json.dumps({"detail": "Failed to generate AI reply"}),
            }

    return EventSourceResponse(event_generator())


@router.post("/{conversation_id}/end", response_model=ConversationEndResponse)
async def end_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """End a conversation and get feedback with XP reward."""
    return await conversation_service.end_conversation(db, current_user, conversation_id)


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's conversation history (paginated, newest first)."""
    return await conversation_service.list_conversations(db, current_user, skip, limit)


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full conversation detail with messages and feedback."""
    return await conversation_service.get_conversation(db, current_user, conversation_id)
