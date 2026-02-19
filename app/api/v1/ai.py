from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_redis
from app.database import get_db
from app.models.user import User
from app.schemas.ai import GenerateCardsRequest, GenerateCardsResponse
from app.services.ai_service import generate_card_set

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post(
    "/generate-cards",
    response_model=GenerateCardsResponse,
    status_code=201,
)
async def generate_cards_endpoint(
    data: GenerateCardsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    card_set = await generate_card_set(db, redis, current_user, data)
    await db.commit()
    return GenerateCardsResponse(
        card_set=card_set,
        generated_count=card_set.card_count,
    )
