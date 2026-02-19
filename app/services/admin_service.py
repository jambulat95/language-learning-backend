import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card, CardSet
from app.models.conversation import AIConversation
from app.models.gamification import UserGamification
from app.models.user import User
from app.schemas.admin import (
    AdminCardSetResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
    PaginatedAdminCardSetResponse,
    PaginatedAdminUserResponse,
    PlatformStatsResponse,
)


async def list_users(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    search: str | None = None,
) -> PaginatedAdminUserResponse:
    base_query = select(User)
    count_query = select(func.count()).select_from(User)

    if search:
        pattern = f"%{search}%"
        filter_clause = or_(
            User.email.ilike(pattern),
            User.full_name.ilike(pattern),
        )
        base_query = base_query.where(filter_clause)
        count_query = count_query.where(filter_clause)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    result = await db.execute(
        base_query.order_by(User.created_at.desc()).offset(skip).limit(limit)
    )
    users = result.scalars().all()

    items = []
    for u in users:
        # Count card sets
        sets_result = await db.execute(
            select(func.count()).select_from(CardSet).where(CardSet.user_id == u.id)
        )
        card_sets_count = sets_result.scalar_one()

        # Get gamification
        gam_result = await db.execute(
            select(UserGamification).where(UserGamification.user_id == u.id)
        )
        gam = gam_result.scalar_one_or_none()

        items.append(
            AdminUserResponse(
                id=u.id,
                email=u.email,
                full_name=u.full_name,
                language_level=u.language_level,
                is_premium=u.is_premium,
                is_active=u.is_active,
                is_admin=u.is_admin,
                created_at=u.created_at,
                card_sets_count=card_sets_count,
                total_xp=gam.total_xp if gam else 0,
                level=gam.level if gam else 1,
                league=gam.league.value if gam else "Bronze",
            )
        )

    return PaginatedAdminUserResponse(
        items=items, total=total, skip=skip, limit=limit
    )


async def update_user_admin(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: AdminUserUpdateRequest,
) -> AdminUserResponse:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if data.is_premium is not None:
        user.is_premium = data.is_premium
    if data.is_active is not None:
        user.is_active = data.is_active

    await db.flush()

    sets_result = await db.execute(
        select(func.count()).select_from(CardSet).where(CardSet.user_id == user.id)
    )
    card_sets_count = sets_result.scalar_one()

    gam_result = await db.execute(
        select(UserGamification).where(UserGamification.user_id == user.id)
    )
    gam = gam_result.scalar_one_or_none()

    return AdminUserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        language_level=user.language_level,
        is_premium=user.is_premium,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
        card_sets_count=card_sets_count,
        total_xp=gam.total_xp if gam else 0,
        level=gam.level if gam else 1,
        league=gam.league.value if gam else "Bronze",
    )


async def delete_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    await db.delete(user)
    await db.flush()


async def list_public_card_sets(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    search: str | None = None,
) -> PaginatedAdminCardSetResponse:
    base_query = select(CardSet).where(CardSet.is_public == True)  # noqa: E712
    count_query = (
        select(func.count()).select_from(CardSet).where(CardSet.is_public == True)  # noqa: E712
    )

    if search:
        pattern = f"%{search}%"
        base_query = base_query.where(CardSet.title.ilike(pattern))
        count_query = count_query.where(CardSet.title.ilike(pattern))

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    result = await db.execute(
        base_query.order_by(CardSet.created_at.desc()).offset(skip).limit(limit)
    )
    card_sets = result.scalars().all()

    items = []
    for cs in card_sets:
        user = await db.get(User, cs.user_id)
        items.append(
            AdminCardSetResponse(
                id=cs.id,
                title=cs.title,
                user_email=user.email if user else "deleted",
                user_full_name=user.full_name if user else "Удалён",
                difficulty_level=cs.difficulty_level,
                card_count=cs.card_count,
                is_public=cs.is_public,
                is_ai_generated=cs.is_ai_generated,
                created_at=cs.created_at,
            )
        )

    return PaginatedAdminCardSetResponse(
        items=items, total=total, skip=skip, limit=limit
    )


async def delete_card_set_admin(db: AsyncSession, set_id: uuid.UUID) -> None:
    card_set = await db.get(CardSet, set_id)
    if card_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Card set not found"
        )
    await db.delete(card_set)
    await db.flush()


async def get_platform_stats(db: AsyncSession) -> PlatformStatsResponse:
    total_users = (
        await db.execute(select(func.count()).select_from(User))
    ).scalar_one()

    premium_users = (
        await db.execute(
            select(func.count()).select_from(User).where(User.is_premium == True)  # noqa: E712
        )
    ).scalar_one()

    total_card_sets = (
        await db.execute(select(func.count()).select_from(CardSet))
    ).scalar_one()

    public_card_sets = (
        await db.execute(
            select(func.count()).select_from(CardSet).where(CardSet.is_public == True)  # noqa: E712
        )
    ).scalar_one()

    total_cards = (
        await db.execute(select(func.count()).select_from(Card))
    ).scalar_one()

    total_conversations = (
        await db.execute(select(func.count()).select_from(AIConversation))
    ).scalar_one()

    today = date.today()
    active_today = (
        await db.execute(
            select(func.count())
            .select_from(UserGamification)
            .where(UserGamification.last_activity_date == today)
        )
    ).scalar_one()

    return PlatformStatsResponse(
        total_users=total_users,
        premium_users=premium_users,
        total_card_sets=total_card_sets,
        public_card_sets=public_card_sets,
        total_cards=total_cards,
        total_conversations=total_conversations,
        active_today=active_today,
    )
