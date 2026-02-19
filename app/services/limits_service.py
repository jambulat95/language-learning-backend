from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.schemas.user import UsageLimitsResponse
from app.services.card_service import count_cards_created_today, count_user_card_sets
from app.services.conversation_service import _count_weekly_conversations


async def get_usage_limits(db: AsyncSession, user: User) -> UsageLimitsResponse:
    card_sets_used = await count_user_card_sets(db, user.id)
    cards_today = await count_cards_created_today(db, user.id)
    ai_dialogues_used = await _count_weekly_conversations(db, user.id)

    return UsageLimitsResponse(
        is_premium=user.is_premium,
        card_sets_used=card_sets_used,
        card_sets_limit=0 if user.is_premium else settings.FREE_MAX_CARD_SETS,
        cards_today=cards_today,
        cards_today_limit=0 if user.is_premium else settings.FREE_MAX_CARDS_PER_DAY,
        ai_dialogues_used=ai_dialogues_used,
        ai_dialogues_limit=0 if user.is_premium else settings.AI_FREE_DIALOGUES_PER_WEEK,
    )
