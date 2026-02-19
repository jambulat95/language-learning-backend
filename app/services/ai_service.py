import hashlib
import json
import logging

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.generator import generate_cards
from app.config import settings
from app.core.gamification_config import XP_AI_GENERATION
from app.models.card import Card, CardSet, CardType
from app.models.gamification import XpEventType
from app.models.user import User
from app.schemas.ai import GenerateCardsRequest, GeneratedCardItem
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


def _build_cache_key(
    topic: str, level: str, count: int, interests: list[str], native_language: str,
) -> str:
    raw = json.dumps({
        "topic": topic.lower().strip(),
        "level": level,
        "count": count,
        "interests": sorted(interests),
        "native_language": native_language,
    }, sort_keys=True)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"ai:cache:{digest}"


async def _check_rate_limit(redis: Redis, user: User) -> None:
    key = f"ai:ratelimit:{user.id}"
    limit = (
        settings.AI_RATE_LIMIT_PREMIUM_PER_MINUTE
        if user.is_premium
        else settings.AI_RATE_LIMIT_PER_MINUTE
    )

    current = await redis.get(key)
    if current is not None and int(current) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI generation rate limit exceeded. Please try again later.",
        )

    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, 60)
    await pipe.execute()


async def generate_card_set(
    db: AsyncSession,
    redis: Redis,
    user: User,
    request: GenerateCardsRequest,
) -> CardSet:
    # Rate limit
    await _check_rate_limit(redis, user)

    native_language = NATIVE_LANGUAGE_MAP.get(user.native_language, user.native_language)
    level = request.difficulty_level.value

    # Check cache
    cache_key = _build_cache_key(
        request.topic, level, request.count, request.interests, native_language,
    )
    cached = await redis.get(cache_key)

    if cached is not None:
        logger.info("Cache hit for key=%s", cache_key)
        items = [GeneratedCardItem(**c) for c in json.loads(cached)]
    else:
        # Generate via LLM
        items = await generate_cards(
            topic=request.topic,
            level=level,
            count=request.count,
            interests=request.interests,
            native_language=native_language,
        )
        # Store in cache
        await redis.set(
            cache_key,
            json.dumps([item.model_dump() for item in items]),
            ex=settings.AI_CACHE_TTL_SECONDS,
        )

    # Save to DB
    card_set = CardSet(
        user_id=user.id,
        title=f"{request.topic} ({level})",
        description=f"AI-generated flashcards on \"{request.topic}\" for level {level}",
        difficulty_level=request.difficulty_level,
        is_ai_generated=True,
        card_count=len(items),
    )
    db.add(card_set)
    await db.flush()

    for idx, item in enumerate(items):
        card = Card(
            card_set_id=card_set.id,
            front_text=item.front_text[:500],
            back_text=item.back_text[:500],
            example_sentence=item.example_sentence,
            card_type=CardType.flashcard,
            order_index=idx,
        )
        db.add(card)

    await db.flush()

    # Award XP for AI generation
    await award_xp(db, user, XP_AI_GENERATION, XpEventType.ai_generation)

    # Reload with cards eagerly loaded
    result = await db.execute(
        select(CardSet)
        .options(selectinload(CardSet.cards))
        .where(CardSet.id == card_set.id)
    )
    return result.scalar_one()
