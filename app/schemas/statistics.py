from datetime import date, datetime

from pydantic import BaseModel


class LevelPrediction(BaseModel):
    current_cefr: str
    next_cefr: str | None
    current_xp: int
    next_cefr_xp: int | None
    avg_daily_xp: float
    estimated_date: date | None


class StatisticsOverview(BaseModel):
    words_learned: int
    words_mastered: int
    accuracy: float
    study_days: int
    level: int
    total_xp: int
    current_streak: int
    level_prediction: LevelPrediction


class DailyActivity(BaseModel):
    date: date
    xp: int
    reviews: int
    cards_learned: int
    conversations: int


class ActivityResponse(BaseModel):
    days: list[DailyActivity]


class WeeklyProgress(BaseModel):
    week_start: date
    xp: int
    reviews: int
    accuracy: float


class ProgressResponse(BaseModel):
    weeks: list[WeeklyProgress]


class SetStrength(BaseModel):
    set_id: str
    set_title: str
    total_cards: int
    cards_studied: int
    correct_reviews: int
    total_reviews: int
    accuracy: float
    mastered_cards: int


class StrengthsResponse(BaseModel):
    sets: list[SetStrength]
