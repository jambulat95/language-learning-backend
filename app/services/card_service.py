import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.gamification_config import XP_SET_CREATED
from app.models.card import Card, CardSet, CardType
from app.models.gamification import XpEventType
from app.models.user import LanguageLevel, User
from app.services.gamification_service import award_xp
from app.schemas.card import (
    CardBulkCreate,
    CardCreate,
    CardSetCreate,
    CardSetUpdate,
    CardUpdate,
)


# --- Helpers ---

async def _update_card_count(db: AsyncSession, card_set_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).where(Card.card_set_id == card_set_id)
    )
    count = result.scalar_one()
    result2 = await db.execute(
        select(CardSet).where(CardSet.id == card_set_id)
    )
    card_set = result2.scalar_one()
    card_set.card_count = count
    await db.flush()
    return count


async def count_user_card_sets(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(CardSet).where(CardSet.user_id == user_id)
    )
    return result.scalar_one()


async def count_cards_created_today(db: AsyncSession, user_id: uuid.UUID) -> int:
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    result = await db.execute(
        select(func.count())
        .select_from(Card)
        .join(CardSet, Card.card_set_id == CardSet.id)
        .where(CardSet.user_id == user_id, Card.created_at >= today_start)
    )
    return result.scalar_one()


async def _check_daily_card_limit(
    db: AsyncSession, user: User, count: int = 1,
) -> None:
    if user.is_premium:
        return
    used = await count_cards_created_today(db, user.id)
    if used + count > settings.FREE_MAX_CARDS_PER_DAY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Daily card limit reached ({settings.FREE_MAX_CARDS_PER_DAY} cards/day for free users).",
        )


async def get_card_set_for_owner(
    db: AsyncSession, set_id: uuid.UUID, user: User,
) -> CardSet:
    result = await db.execute(
        select(CardSet)
        .options(selectinload(CardSet.cards))
        .where(CardSet.id == set_id)
    )
    card_set = result.scalar_one_or_none()
    if card_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card set not found",
        )
    if card_set.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this card set",
        )
    return card_set


async def get_card_set_or_public(
    db: AsyncSession, set_id: uuid.UUID, user: User,
) -> CardSet:
    result = await db.execute(
        select(CardSet)
        .options(selectinload(CardSet.cards))
        .where(CardSet.id == set_id)
    )
    card_set = result.scalar_one_or_none()
    if card_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card set not found",
        )
    if card_set.user_id != user.id and not card_set.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    return card_set


# --- CardSet CRUD ---

async def create_card_set(
    db: AsyncSession, data: CardSetCreate, user: User,
) -> CardSet:
    if not user.is_premium:
        current_count = await count_user_card_sets(db, user.id)
        if current_count >= settings.FREE_MAX_CARD_SETS:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Card set limit reached ({settings.FREE_MAX_CARD_SETS} sets for free users).",
            )

    card_set = CardSet(
        user_id=user.id,
        **data.model_dump(),
    )
    db.add(card_set)
    await db.flush()

    # Award XP for creating a set
    await award_xp(db, user, XP_SET_CREATED, XpEventType.set_created)

    result = await db.execute(
        select(CardSet)
        .options(selectinload(CardSet.cards))
        .where(CardSet.id == card_set.id)
    )
    return result.scalar_one()


async def list_user_card_sets(
    db: AsyncSession,
    user: User,
    skip: int = 0,
    limit: int = 20,
    q: str | None = None,
    category: str | None = None,
    difficulty_level: LanguageLevel | None = None,
) -> tuple[list[CardSet], int]:
    query = select(CardSet).where(CardSet.user_id == user.id)
    count_query = select(func.count()).select_from(CardSet).where(CardSet.user_id == user.id)

    if q:
        pattern = f"%{q}%"
        filter_clause = CardSet.title.ilike(pattern) | CardSet.description.ilike(pattern)
        query = query.where(filter_clause)
        count_query = count_query.where(filter_clause)

    if category:
        query = query.where(CardSet.category == category)
        count_query = count_query.where(CardSet.category == category)

    if difficulty_level:
        query = query.where(CardSet.difficulty_level == difficulty_level)
        count_query = count_query.where(CardSet.difficulty_level == difficulty_level)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = query.order_by(CardSet.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return items, total


async def list_public_card_sets(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    q: str | None = None,
    category: str | None = None,
    difficulty_level: LanguageLevel | None = None,
) -> tuple[list[CardSet], int]:
    query = select(CardSet).where(CardSet.is_public.is_(True))
    count_query = select(func.count()).select_from(CardSet).where(CardSet.is_public.is_(True))

    if q:
        pattern = f"%{q}%"
        filter_clause = CardSet.title.ilike(pattern) | CardSet.description.ilike(pattern)
        query = query.where(filter_clause)
        count_query = count_query.where(filter_clause)

    if category:
        query = query.where(CardSet.category == category)
        count_query = count_query.where(CardSet.category == category)

    if difficulty_level:
        query = query.where(CardSet.difficulty_level == difficulty_level)
        count_query = count_query.where(CardSet.difficulty_level == difficulty_level)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = query.order_by(CardSet.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return items, total


async def update_card_set(
    db: AsyncSession, card_set: CardSet, data: CardSetUpdate,
) -> CardSet:
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(card_set, field, value)
    await db.flush()

    result = await db.execute(
        select(CardSet)
        .options(selectinload(CardSet.cards))
        .where(CardSet.id == card_set.id)
    )
    return result.scalar_one()


async def delete_card_set(db: AsyncSession, card_set: CardSet) -> None:
    await db.delete(card_set)
    await db.flush()


# --- Card CRUD ---

async def create_card(
    db: AsyncSession, card_set: CardSet, data: CardCreate, user: User,
) -> Card:
    await _check_daily_card_limit(db, user, count=1)

    card = Card(
        card_set_id=card_set.id,
        **data.model_dump(),
    )
    db.add(card)
    await db.flush()
    await _update_card_count(db, card_set.id)
    return card


async def list_cards(
    db: AsyncSession,
    card_set: CardSet,
    skip: int = 0,
    limit: int = 50,
    q: str | None = None,
    card_type: CardType | None = None,
) -> tuple[list[Card], int]:
    query = select(Card).where(Card.card_set_id == card_set.id)
    count_query = select(func.count()).select_from(Card).where(Card.card_set_id == card_set.id)

    if q:
        pattern = f"%{q}%"
        filter_clause = Card.front_text.ilike(pattern) | Card.back_text.ilike(pattern)
        query = query.where(filter_clause)
        count_query = count_query.where(filter_clause)

    if card_type:
        query = query.where(Card.card_type == card_type)
        count_query = count_query.where(Card.card_type == card_type)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = query.order_by(Card.order_index, Card.created_at).offset(skip).limit(limit)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return items, total


async def get_card(
    db: AsyncSession, card_set: CardSet, card_id: uuid.UUID,
) -> Card:
    result = await db.execute(
        select(Card).where(Card.id == card_id, Card.card_set_id == card_set.id)
    )
    card = result.scalar_one_or_none()
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found",
        )
    return card


async def update_card(
    db: AsyncSession, card: Card, data: CardUpdate,
) -> Card:
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(card, field, value)
    await db.flush()
    return card


async def delete_card(db: AsyncSession, card: Card) -> None:
    card_set_id = card.card_set_id
    await db.delete(card)
    await db.flush()
    await _update_card_count(db, card_set_id)


async def bulk_create_cards(
    db: AsyncSession, card_set: CardSet, data: CardBulkCreate, user: User,
) -> list[Card]:
    await _check_daily_card_limit(db, user, count=len(data.cards))

    cards = []
    for card_data in data.cards:
        card = Card(
            card_set_id=card_set.id,
            **card_data.model_dump(),
        )
        db.add(card)
        cards.append(card)
    await db.flush()
    await _update_card_count(db, card_set.id)
    return cards


async def import_cards_from_file(
    db: AsyncSession, card_set: CardSet, file: UploadFile, user: User,
) -> tuple[list[Card], int]:
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    # Detect delimiter
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t|;")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty",
        )

    # Heuristic: skip header if first row looks like labels
    start = 0
    if rows[0] and rows[0][0].lower().strip() in (
        "front", "front_text", "word", "term", "question",
    ):
        start = 1

    # Parse valid rows
    valid_rows: list[tuple[str, str, str | None]] = []
    skipped = 0
    for row in rows[start:]:
        if len(row) < 2:
            skipped += 1
            continue
        front = row[0].strip()
        back = row[1].strip()
        if not front or not back:
            skipped += 1
            continue
        example = row[2].strip() if len(row) > 2 and row[2].strip() else None
        valid_rows.append((front[:500], back[:500], example))

    # Check daily card limit before inserting
    await _check_daily_card_limit(db, user, count=len(valid_rows))

    cards: list[Card] = []
    for i, (front, back, example) in enumerate(valid_rows):
        card = Card(
            card_set_id=card_set.id,
            front_text=front,
            back_text=back,
            example_sentence=example,
            card_type=CardType.flashcard,
            order_index=i,
        )
        db.add(card)
        cards.append(card)

    await db.flush()
    await _update_card_count(db, card_set.id)
    return cards, skipped
