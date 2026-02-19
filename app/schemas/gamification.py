import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.gamification import AchievementCondition, League


class AchievementResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    icon_url: str | None
    condition_type: AchievementCondition
    condition_value: int
    xp_reward: int
    unlocked_at: datetime | None = None

    model_config = {"from_attributes": True}


class XpAwardResult(BaseModel):
    total_xp: int
    level: int
    league: League
    current_streak: int
    xp_earned: int
    new_achievements: list[AchievementResponse]


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: uuid.UUID
    full_name: str
    avatar_url: str | None
    total_xp: int
    level: int
    league: League


class LeaderboardResponse(BaseModel):
    entries: list[LeaderboardEntry]
    period: str
    user_rank: int | None = None


class GamificationProfileResponse(BaseModel):
    total_xp: int
    level: int
    league: League
    current_streak: int
    longest_streak: int
    today_xp: int
    daily_xp_goal: int
    achievements_unlocked: int
