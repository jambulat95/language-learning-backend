from datetime import datetime, timezone

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card, CardSet
from app.models.gamification import League, UserGamification
from app.models.progress import UserCardProgress
from app.models.user import User
from app.services.gamification_service import get_today_xp
from app.schemas.dashboard import (
    DashboardCardSetItem,
    DashboardGamification,
    DashboardResponse,
)


async def get_dashboard_data(
    db: AsyncSession, user: User
) -> DashboardResponse:
    # 1. Gamification stats
    result = await db.execute(
        select(UserGamification).where(UserGamification.user_id == user.id)
    )
    gam = result.scalar_one_or_none()

    gamification = DashboardGamification(
        total_xp=gam.total_xp if gam else 0,
        level=gam.level if gam else 1,
        current_streak=gam.current_streak if gam else 0,
        longest_streak=gam.longest_streak if gam else 0,
        league=gam.league if gam else League.Bronze,
    )

    # 2. Today's reviews count
    today = datetime.now(timezone.utc).date()
    today_reviews_result = await db.execute(
        select(func.count())
        .select_from(UserCardProgress)
        .where(
            UserCardProgress.user_id == user.id,
            func.date(UserCardProgress.last_reviewed_at) == today,
        )
    )
    today_reviews = today_reviews_result.scalar_one()

    # 3. Today's XP (from actual XP events)
    today_xp = await get_today_xp(db, user.id)

    # 4. Recent card sets (5 most recently updated)
    sets_result = await db.execute(
        select(CardSet)
        .where(CardSet.user_id == user.id)
        .order_by(CardSet.updated_at.desc())
        .limit(5)
    )
    recent_card_sets = sets_result.scalars().all()

    now = datetime.now(timezone.utc)

    # 5. Per-set progress (batched)
    recent_sets: list[DashboardCardSetItem] = []
    if recent_card_sets:
        set_ids = [cs.id for cs in recent_card_sets]

        # Learned cards per set
        learned_query = (
            select(
                Card.card_set_id,
                func.count().label("learned"),
            )
            .join(UserCardProgress, UserCardProgress.card_id == Card.id)
            .where(
                UserCardProgress.user_id == user.id,
                Card.card_set_id.in_(set_ids),
            )
            .group_by(Card.card_set_id)
        )
        learned_result = await db.execute(learned_query)
        learned_map = {row.card_set_id: row.learned for row in learned_result}

        # Due cards per set (next_review_date <= now OR never reviewed)
        due_reviewed_query = (
            select(
                Card.card_set_id,
                func.count().label("due"),
            )
            .join(UserCardProgress, UserCardProgress.card_id == Card.id)
            .where(
                UserCardProgress.user_id == user.id,
                Card.card_set_id.in_(set_ids),
                UserCardProgress.next_review_date <= now,
            )
            .group_by(Card.card_set_id)
        )
        due_reviewed_result = await db.execute(due_reviewed_query)
        due_reviewed_map = {
            row.card_set_id: row.due for row in due_reviewed_result
        }

        # New (never reviewed) cards per set
        new_cards_query = (
            select(
                Card.card_set_id,
                func.count().label("new_count"),
            )
            .outerjoin(
                UserCardProgress,
                (UserCardProgress.card_id == Card.id)
                & (UserCardProgress.user_id == user.id),
            )
            .where(
                Card.card_set_id.in_(set_ids),
                UserCardProgress.id.is_(None),
            )
            .group_by(Card.card_set_id)
        )
        new_cards_result = await db.execute(new_cards_query)
        new_cards_map = {
            row.card_set_id: row.new_count for row in new_cards_result
        }

        for cs in recent_card_sets:
            due = due_reviewed_map.get(cs.id, 0) + new_cards_map.get(cs.id, 0)
            recent_sets.append(
                DashboardCardSetItem(
                    id=cs.id,
                    title=cs.title,
                    category=cs.category,
                    difficulty_level=cs.difficulty_level,
                    card_count=cs.card_count,
                    learned_cards=learned_map.get(cs.id, 0),
                    due_cards=due,
                    updated_at=cs.updated_at,
                )
            )

    # 6. Totals across all user sets
    total_learned_result = await db.execute(
        select(func.count())
        .select_from(UserCardProgress)
        .join(Card, Card.id == UserCardProgress.card_id)
        .join(CardSet, CardSet.id == Card.card_set_id)
        .where(
            UserCardProgress.user_id == user.id,
            CardSet.user_id == user.id,
        )
    )
    total_cards_learned = total_learned_result.scalar_one()

    total_due_reviewed_result = await db.execute(
        select(func.count())
        .select_from(UserCardProgress)
        .join(Card, Card.id == UserCardProgress.card_id)
        .join(CardSet, CardSet.id == Card.card_set_id)
        .where(
            UserCardProgress.user_id == user.id,
            CardSet.user_id == user.id,
            UserCardProgress.next_review_date <= now,
        )
    )
    total_due_reviewed = total_due_reviewed_result.scalar_one()

    total_new_result = await db.execute(
        select(func.count())
        .select_from(Card)
        .join(CardSet, CardSet.id == Card.card_set_id)
        .outerjoin(
            UserCardProgress,
            (UserCardProgress.card_id == Card.id)
            & (UserCardProgress.user_id == user.id),
        )
        .where(
            CardSet.user_id == user.id,
            UserCardProgress.id.is_(None),
        )
    )
    total_new = total_new_result.scalar_one()
    total_due_cards = total_due_reviewed + total_new

    return DashboardResponse(
        gamification=gamification,
        today_xp=today_xp,
        daily_xp_goal=user.daily_xp_goal,
        today_reviews=today_reviews,
        recent_sets=recent_sets,
        total_cards_learned=total_cards_learned,
        total_due_cards=total_due_cards,
    )
