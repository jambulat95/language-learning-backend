import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.card import CardType
from app.models.gamification import League
from app.models.user import LanguageLevel


class DashboardGamification(BaseModel):
    total_xp: int
    level: int
    current_streak: int
    longest_streak: int
    league: League


class DashboardCardSetItem(BaseModel):
    id: uuid.UUID
    title: str
    category: str | None
    difficulty_level: LanguageLevel
    card_count: int
    learned_cards: int
    due_cards: int
    updated_at: datetime | None


class DashboardResponse(BaseModel):
    gamification: DashboardGamification
    today_xp: int
    daily_xp_goal: int
    today_reviews: int
    recent_sets: list[DashboardCardSetItem]
    total_cards_learned: int
    total_due_cards: int
