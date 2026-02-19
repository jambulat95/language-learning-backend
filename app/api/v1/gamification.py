from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.gamification import UserAchievement, UserGamification
from app.models.user import User
from app.schemas.gamification import (
    AchievementResponse,
    GamificationProfileResponse,
    LeaderboardEntry,
    LeaderboardResponse,
)
from app.services.gamification_service import (
    get_leaderboard,
    get_today_xp,
    get_user_achievements,
)

router = APIRouter(prefix="/gamification", tags=["gamification"])


@router.get("/profile", response_model=GamificationProfileResponse)
async def get_gamification_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserGamification).where(UserGamification.user_id == current_user.id)
    )
    gam = result.scalar_one_or_none()

    today_xp = await get_today_xp(db, current_user.id)

    # Count unlocked achievements
    unlocked_result = await db.execute(
        select(func.count())
        .select_from(UserAchievement)
        .where(UserAchievement.user_id == current_user.id)
    )
    achievements_unlocked = unlocked_result.scalar_one()

    return GamificationProfileResponse(
        total_xp=gam.total_xp if gam else 0,
        level=gam.level if gam else 1,
        league=gam.league if gam else "Bronze",
        current_streak=gam.current_streak if gam else 0,
        longest_streak=gam.longest_streak if gam else 0,
        today_xp=today_xp,
        daily_xp_goal=current_user.daily_xp_goal,
        achievements_unlocked=achievements_unlocked,
    )


@router.get("/achievements", response_model=list[AchievementResponse])
async def get_achievements(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_user_achievements(db, current_user.id)


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard_endpoint(
    period: str = Query("weekly", pattern="^(weekly|monthly|all_time)$"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entries, user_rank = await get_leaderboard(
        db, period, limit=limit, current_user_id=current_user.id,
    )
    return LeaderboardResponse(
        entries=[LeaderboardEntry(**e) for e in entries],
        period=period,
        user_rank=user_rank,
    )
