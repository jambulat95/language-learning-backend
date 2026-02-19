import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.gamification_config import (
    LEAGUE_THRESHOLDS,
    LEVEL_INCREMENT_AFTER_10,
    LEVEL_THRESHOLDS,
)
from app.models.card import CardSet
from app.models.gamification import (
    Achievement,
    AchievementCondition,
    League,
    UserAchievement,
    UserGamification,
    XpEvent,
    XpEventType,
)
from app.models.progress import UserCardProgress
from app.models.user import User
from app.schemas.gamification import AchievementResponse, XpAwardResult


def calculate_level(total_xp: int) -> int:
    """Calculate user level based on total XP."""
    # Walk thresholds for levels 1-10
    for i in range(len(LEVEL_THRESHOLDS) - 1, -1, -1):
        if total_xp >= LEVEL_THRESHOLDS[i]:
            if i < len(LEVEL_THRESHOLDS) - 1:
                return i + 1
            # Beyond level 10
            return 10 + (total_xp - LEVEL_THRESHOLDS[-1]) // LEVEL_INCREMENT_AFTER_10
    return 1


def calculate_league(total_xp: int) -> League:
    """Calculate user league based on total XP."""
    for threshold, league in LEAGUE_THRESHOLDS:
        if total_xp >= threshold:
            return league
    return League.Bronze


def update_streak(gamification: UserGamification, today: date) -> None:
    """Update user's activity streak."""
    if gamification.last_activity_date == today:
        return

    yesterday = today - timedelta(days=1)
    if gamification.last_activity_date == yesterday:
        gamification.current_streak += 1
    else:
        gamification.current_streak = 1

    gamification.longest_streak = max(
        gamification.current_streak, gamification.longest_streak
    )
    gamification.last_activity_date = today


async def check_achievements(
    db: AsyncSession,
    user: User,
    gamification: UserGamification,
) -> list[Achievement]:
    """Check and unlock any newly earned achievements."""
    # Get achievements user hasn't earned yet
    earned_ids_query = select(UserAchievement.achievement_id).where(
        UserAchievement.user_id == user.id
    )
    result = await db.execute(
        select(Achievement).where(Achievement.id.notin_(earned_ids_query))
    )
    unearned = result.scalars().all()

    if not unearned:
        return []

    # Pre-compute counts needed for condition checks
    condition_values: dict[AchievementCondition, int] = {}

    # Check which condition types we need
    needed_types = {a.condition_type for a in unearned}

    if AchievementCondition.cards_learned in needed_types:
        count_result = await db.execute(
            select(func.count())
            .select_from(UserCardProgress)
            .where(UserCardProgress.user_id == user.id)
        )
        condition_values[AchievementCondition.cards_learned] = count_result.scalar_one()

    if AchievementCondition.streak_days in needed_types:
        condition_values[AchievementCondition.streak_days] = gamification.current_streak

    if AchievementCondition.xp_earned in needed_types:
        condition_values[AchievementCondition.xp_earned] = gamification.total_xp

    if AchievementCondition.sets_created in needed_types:
        count_result = await db.execute(
            select(func.count())
            .select_from(CardSet)
            .where(CardSet.user_id == user.id)
        )
        condition_values[AchievementCondition.sets_created] = count_result.scalar_one()

    if AchievementCondition.conversations in needed_types:
        from app.models.conversation import AIConversation
        count_result = await db.execute(
            select(func.count()).select_from(AIConversation)
            .where(AIConversation.user_id == user.id, AIConversation.ended_at.isnot(None))
        )
        condition_values[AchievementCondition.conversations] = count_result.scalar_one()

    if AchievementCondition.perfect_reviews in needed_types:
        # Count reviews where rating was "easy" (quality 5 = all correct)
        count_result = await db.execute(
            select(func.coalesce(func.sum(UserCardProgress.correct_reviews), 0))
            .where(UserCardProgress.user_id == user.id)
        )
        condition_values[AchievementCondition.perfect_reviews] = count_result.scalar_one()

    if AchievementCondition.friends_count in needed_types:
        from app.models.friendship import Friendship, FriendshipStatus
        count_result = await db.execute(
            select(func.count())
            .select_from(Friendship)
            .where(
                or_(
                    Friendship.user_id == user.id,
                    Friendship.friend_id == user.id,
                ),
                Friendship.status == FriendshipStatus.accepted,
            )
        )
        condition_values[AchievementCondition.friends_count] = count_result.scalar_one()

    # Check each unearned achievement
    newly_unlocked: list[Achievement] = []
    for achievement in unearned:
        current_value = condition_values.get(achievement.condition_type, 0)
        if current_value >= achievement.condition_value:
            # Unlock it
            user_achievement = UserAchievement(
                user_id=user.id,
                achievement_id=achievement.id,
            )
            db.add(user_achievement)

            # Award bonus XP (without re-triggering achievement check)
            if achievement.xp_reward > 0:
                bonus_event = XpEvent(
                    user_id=user.id,
                    xp_amount=achievement.xp_reward,
                    event_type=XpEventType.achievement_bonus,
                )
                db.add(bonus_event)
                gamification.total_xp += achievement.xp_reward

            newly_unlocked.append(achievement)

    if newly_unlocked:
        # Recalculate level/league after bonus XP
        gamification.level = calculate_level(gamification.total_xp)
        gamification.league = calculate_league(gamification.total_xp)
        await db.flush()

    return newly_unlocked


async def _get_or_create_gamification(
    db: AsyncSession, user: User,
) -> UserGamification:
    """Get existing or create new UserGamification record."""
    result = await db.execute(
        select(UserGamification).where(UserGamification.user_id == user.id)
    )
    gam = result.scalar_one_or_none()
    if gam is None:
        gam = UserGamification(user_id=user.id)
        db.add(gam)
        await db.flush()
    return gam


async def award_xp(
    db: AsyncSession,
    user: User,
    xp_amount: int,
    event_type: XpEventType,
) -> XpAwardResult:
    """Award XP to a user and update all gamification state."""
    gamification = await _get_or_create_gamification(db, user)

    # Create XP event record
    xp_event = XpEvent(
        user_id=user.id,
        xp_amount=xp_amount,
        event_type=event_type,
    )
    db.add(xp_event)

    # Update total XP
    gamification.total_xp += xp_amount

    # Update level and league
    gamification.level = calculate_level(gamification.total_xp)
    gamification.league = calculate_league(gamification.total_xp)

    # Update streak
    today = datetime.now(timezone.utc).date()
    update_streak(gamification, today)

    # Check achievements
    newly_unlocked = await check_achievements(db, user, gamification)

    await db.flush()

    # Build achievement responses
    achievement_responses = []
    for achievement in newly_unlocked:
        # Find unlock time
        ua_result = await db.execute(
            select(UserAchievement).where(
                UserAchievement.user_id == user.id,
                UserAchievement.achievement_id == achievement.id,
            )
        )
        ua = ua_result.scalar_one()
        achievement_responses.append(
            AchievementResponse(
                id=achievement.id,
                title=achievement.title,
                description=achievement.description,
                icon_url=achievement.icon_url,
                condition_type=achievement.condition_type,
                condition_value=achievement.condition_value,
                xp_reward=achievement.xp_reward,
                unlocked_at=ua.unlocked_at,
            )
        )

    return XpAwardResult(
        total_xp=gamification.total_xp,
        level=gamification.level,
        league=gamification.league,
        current_streak=gamification.current_streak,
        xp_earned=xp_amount,
        new_achievements=achievement_responses,
    )


async def get_today_xp(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Get total XP earned today."""
    today = datetime.now(timezone.utc).date()
    result = await db.execute(
        select(func.coalesce(func.sum(XpEvent.xp_amount), 0)).where(
            XpEvent.user_id == user_id,
            func.date(XpEvent.created_at) == today,
        )
    )
    return result.scalar_one()


async def get_leaderboard(
    db: AsyncSession,
    period: str,
    limit: int = 50,
    current_user_id: uuid.UUID | None = None,
) -> tuple[list[dict], int | None]:
    """Get leaderboard entries. Returns (entries, user_rank)."""
    if period == "all_time":
        query = (
            select(
                UserGamification.user_id,
                User.full_name,
                User.avatar_url,
                UserGamification.total_xp,
                UserGamification.level,
                UserGamification.league,
            )
            .join(User, User.id == UserGamification.user_id)
            .order_by(UserGamification.total_xp.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        rows = result.all()

        entries = []
        user_rank = None
        for idx, row in enumerate(rows, 1):
            entries.append({
                "rank": idx,
                "user_id": row.user_id,
                "full_name": row.full_name,
                "avatar_url": row.avatar_url,
                "total_xp": row.total_xp,
                "level": row.level,
                "league": row.league,
            })
            if current_user_id and row.user_id == current_user_id:
                user_rank = idx

        # If user not in top N, find their rank
        if current_user_id and user_rank is None:
            gam_result = await db.execute(
                select(UserGamification.total_xp).where(
                    UserGamification.user_id == current_user_id
                )
            )
            user_xp = gam_result.scalar_one_or_none()
            if user_xp is not None:
                rank_result = await db.execute(
                    select(func.count()).select_from(UserGamification).where(
                        UserGamification.total_xp > user_xp
                    )
                )
                user_rank = rank_result.scalar_one() + 1

        return entries, user_rank
    else:
        # Period-based: sum xp_events within date range
        if period == "weekly":
            days = 7
        else:  # monthly
            days = 30

        since = datetime.now(timezone.utc) - timedelta(days=days)

        query = (
            select(
                XpEvent.user_id,
                User.full_name,
                User.avatar_url,
                func.sum(XpEvent.xp_amount).label("total_xp"),
                UserGamification.level,
                UserGamification.league,
            )
            .join(User, User.id == XpEvent.user_id)
            .outerjoin(
                UserGamification, UserGamification.user_id == XpEvent.user_id
            )
            .where(XpEvent.created_at >= since)
            .group_by(
                XpEvent.user_id,
                User.full_name,
                User.avatar_url,
                UserGamification.level,
                UserGamification.league,
            )
            .order_by(func.sum(XpEvent.xp_amount).desc())
            .limit(limit)
        )
        result = await db.execute(query)
        rows = result.all()

        entries = []
        user_rank = None
        for idx, row in enumerate(rows, 1):
            entries.append({
                "rank": idx,
                "user_id": row.user_id,
                "full_name": row.full_name,
                "avatar_url": row.avatar_url,
                "total_xp": row.total_xp,
                "level": row.level or 1,
                "league": row.league or League.Bronze,
            })
            if current_user_id and row.user_id == current_user_id:
                user_rank = idx

        return entries, user_rank


async def get_user_achievements(
    db: AsyncSession, user_id: uuid.UUID,
) -> list[AchievementResponse]:
    """Get all achievements with user's unlock status."""
    # Get all achievements
    result = await db.execute(select(Achievement).order_by(Achievement.condition_type, Achievement.condition_value))
    all_achievements = result.scalars().all()

    # Get user's unlocked achievements
    ua_result = await db.execute(
        select(UserAchievement).where(UserAchievement.user_id == user_id)
    )
    user_achievements = {ua.achievement_id: ua for ua in ua_result.scalars().all()}

    responses = []
    for achievement in all_achievements:
        ua = user_achievements.get(achievement.id)
        responses.append(
            AchievementResponse(
                id=achievement.id,
                title=achievement.title,
                description=achievement.description,
                icon_url=achievement.icon_url,
                condition_type=achievement.condition_type,
                condition_value=achievement.condition_value,
                xp_reward=achievement.xp_reward,
                unlocked_at=ua.unlocked_at if ua else None,
            )
        )

    return responses
