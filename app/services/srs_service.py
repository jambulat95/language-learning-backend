import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card
from app.models.progress import UserCardProgress
from app.models.user import User
from app.core.gamification_config import XP_REVIEW_BASE, XP_REVIEW_BONUS
from app.models.gamification import XpEventType
from app.schemas.srs import (
    RATING_TO_QUALITY,
    AchievementUnlock,
    CardProgressResponse,
    ReviewRating,
    ReviewResponse,
    StudyCardResponse,
    StudySetProgressResponse,
)
from app.services.card_service import get_card_set_or_public
from app.services.gamification_service import award_xp


# --- SM-2 Algorithm ---

@dataclass
class SM2Result:
    ease_factor: float
    interval: int
    repetitions: int


def calculate_sm2(
    ease_factor: float,
    interval: int,
    repetitions: int,
    quality: int,
) -> SM2Result:
    """SM-2 spaced repetition algorithm.

    Args:
        ease_factor: Current ease factor (>= 1.3).
        interval: Current interval in days.
        repetitions: Number of consecutive correct reviews.
        quality: Response quality (0-5).

    Returns:
        SM2Result with updated values.
    """
    # Update ease factor
    new_ef = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_ef = max(new_ef, 1.3)

    if quality >= 3:
        # Correct response
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = round(interval * new_ef)
        new_repetitions = repetitions + 1
    else:
        # Incorrect — reset
        new_interval = 1
        new_repetitions = 0

    return SM2Result(
        ease_factor=new_ef,
        interval=new_interval,
        repetitions=new_repetitions,
    )


# --- Service functions ---

async def get_due_cards(
    db: AsyncSession,
    user: User,
    set_id: uuid.UUID,
    limit: int = 20,
    new_first: bool = True,
    practice: bool = False,
) -> list[StudyCardResponse]:
    """Get cards due for review, including new (unreviewed) cards.

    If practice=True, returns ALL cards in the set regardless of SRS schedule.
    """
    card_set = await get_card_set_or_public(db, set_id, user)

    if practice:
        query = (
            select(Card, UserCardProgress)
            .outerjoin(
                UserCardProgress,
                (UserCardProgress.card_id == Card.id)
                & (UserCardProgress.user_id == user.id),
            )
            .where(Card.card_set_id == card_set.id)
            .order_by(Card.order_index, Card.created_at)
            .limit(limit)
        )
        result = await db.execute(query)
        return [
            StudyCardResponse(
                id=card.id,
                card_set_id=card.card_set_id,
                front_text=card.front_text,
                back_text=card.back_text,
                example_sentence=card.example_sentence,
                image_url=card.image_url,
                audio_url=card.audio_url,
                card_type=card.card_type,
                order_index=card.order_index,
                created_at=card.created_at,
                progress=CardProgressResponse.model_validate(progress) if progress else None,
            )
            for card, progress in result.tuples().all()
        ]

    now = datetime.now(timezone.utc)
    results: list[StudyCardResponse] = []

    if new_first:
        # Cards that have never been reviewed by this user
        new_cards_query = (
            select(Card)
            .outerjoin(
                UserCardProgress,
                (UserCardProgress.card_id == Card.id)
                & (UserCardProgress.user_id == user.id),
            )
            .where(
                Card.card_set_id == card_set.id,
                UserCardProgress.id.is_(None),
            )
            .order_by(Card.order_index, Card.created_at)
            .limit(limit)
        )
        new_result = await db.execute(new_cards_query)
        for card in new_result.scalars().all():
            results.append(StudyCardResponse(
                id=card.id,
                card_set_id=card.card_set_id,
                front_text=card.front_text,
                back_text=card.back_text,
                example_sentence=card.example_sentence,
                image_url=card.image_url,
                audio_url=card.audio_url,
                card_type=card.card_type,
                order_index=card.order_index,
                created_at=card.created_at,
                progress=None,
            ))

    remaining = limit - len(results)
    if remaining > 0:
        # Cards due for review (next_review_date <= now)
        due_query = (
            select(Card, UserCardProgress)
            .join(
                UserCardProgress,
                (UserCardProgress.card_id == Card.id)
                & (UserCardProgress.user_id == user.id),
            )
            .where(
                Card.card_set_id == card_set.id,
                UserCardProgress.next_review_date <= now,
            )
            .order_by(UserCardProgress.next_review_date.asc())
            .limit(remaining)
        )
        due_result = await db.execute(due_query)
        for card, progress in due_result.tuples().all():
            results.append(StudyCardResponse(
                id=card.id,
                card_set_id=card.card_set_id,
                front_text=card.front_text,
                back_text=card.back_text,
                example_sentence=card.example_sentence,
                image_url=card.image_url,
                audio_url=card.audio_url,
                card_type=card.card_type,
                order_index=card.order_index,
                created_at=card.created_at,
                progress=CardProgressResponse.model_validate(progress),
            ))

    return results


async def submit_review(
    db: AsyncSession,
    user: User,
    card_id: uuid.UUID,
    rating: ReviewRating,
) -> ReviewResponse:
    """Submit a review for a card and apply SM-2 algorithm."""
    # Verify the card exists
    card_result = await db.execute(select(Card).where(Card.id == card_id))
    card = card_result.scalar_one_or_none()
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found",
        )

    # Verify user has access to the card's set
    await get_card_set_or_public(db, card.card_set_id, user)

    # Find or create progress record
    progress_result = await db.execute(
        select(UserCardProgress).where(
            UserCardProgress.user_id == user.id,
            UserCardProgress.card_id == card_id,
        )
    )
    progress = progress_result.scalar_one_or_none()

    quality = RATING_TO_QUALITY[rating]
    now = datetime.now(timezone.utc)

    if progress is None:
        # First review of this card
        sm2 = calculate_sm2(
            ease_factor=2.5, interval=0, repetitions=0, quality=quality,
        )
        progress = UserCardProgress(
            user_id=user.id,
            card_id=card_id,
            ease_factor=sm2.ease_factor,
            interval=sm2.interval,
            repetitions=sm2.repetitions,
            next_review_date=now + timedelta(days=sm2.interval),
            last_reviewed_at=now,
            total_reviews=1,
            correct_reviews=1 if quality >= 3 else 0,
        )
        db.add(progress)
    else:
        sm2 = calculate_sm2(
            ease_factor=progress.ease_factor,
            interval=progress.interval,
            repetitions=progress.repetitions,
            quality=quality,
        )
        progress.ease_factor = sm2.ease_factor
        progress.interval = sm2.interval
        progress.repetitions = sm2.repetitions
        progress.next_review_date = now + timedelta(days=sm2.interval)
        progress.last_reviewed_at = now
        progress.total_reviews += 1
        if quality >= 3:
            progress.correct_reviews += 1

    await db.flush()

    # Award XP
    xp_amount = XP_REVIEW_BASE + XP_REVIEW_BONUS.get(rating.value, 0)
    xp_result = await award_xp(db, user, xp_amount, XpEventType.review)

    return ReviewResponse(
        card_id=card_id,
        ease_factor=sm2.ease_factor,
        interval=sm2.interval,
        next_review_date=progress.next_review_date,
        is_correct=quality >= 3,
        xp_earned=xp_result.xp_earned,
        new_achievements=[
            AchievementUnlock(id=a.id, title=a.title, xp_reward=a.xp_reward)
            for a in xp_result.new_achievements
        ],
    )


async def get_set_study_progress(
    db: AsyncSession,
    user: User,
    set_id: uuid.UUID,
) -> StudySetProgressResponse:
    """Get study progress summary for a card set."""
    card_set = await get_card_set_or_public(db, set_id, user)
    now = datetime.now(timezone.utc)

    # Total cards in the set
    total_result = await db.execute(
        select(func.count()).where(Card.card_set_id == card_set.id)
    )
    total_cards = total_result.scalar_one()

    # Cards with at least one review (learned)
    learned_result = await db.execute(
        select(func.count())
        .select_from(UserCardProgress)
        .join(Card, Card.id == UserCardProgress.card_id)
        .where(
            UserCardProgress.user_id == user.id,
            Card.card_set_id == card_set.id,
        )
    )
    learned_cards = learned_result.scalar_one()

    # Due cards (next_review_date <= now)
    due_result = await db.execute(
        select(func.count())
        .select_from(UserCardProgress)
        .join(Card, Card.id == UserCardProgress.card_id)
        .where(
            UserCardProgress.user_id == user.id,
            Card.card_set_id == card_set.id,
            UserCardProgress.next_review_date <= now,
        )
    )
    due_cards = due_result.scalar_one()

    # Add new cards (never reviewed) to due count
    new_cards_result = await db.execute(
        select(func.count())
        .select_from(Card)
        .outerjoin(
            UserCardProgress,
            (UserCardProgress.card_id == Card.id)
            & (UserCardProgress.user_id == user.id),
        )
        .where(
            Card.card_set_id == card_set.id,
            UserCardProgress.id.is_(None),
        )
    )
    new_cards = new_cards_result.scalar_one()
    due_cards += new_cards

    # Mastered cards (interval >= 21 days)
    mastered_result = await db.execute(
        select(func.count())
        .select_from(UserCardProgress)
        .join(Card, Card.id == UserCardProgress.card_id)
        .where(
            UserCardProgress.user_id == user.id,
            Card.card_set_id == card_set.id,
            UserCardProgress.interval >= 21,
        )
    )
    mastered_cards = mastered_result.scalar_one()

    return StudySetProgressResponse(
        total_cards=total_cards,
        learned_cards=learned_cards,
        due_cards=due_cards,
        mastered_cards=mastered_cards,
    )
