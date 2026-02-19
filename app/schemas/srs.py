import enum
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.card import CardType


class ReviewRating(str, enum.Enum):
    again = "again"   # quality = 0
    hard = "hard"     # quality = 3
    good = "good"     # quality = 4
    easy = "easy"     # quality = 5


RATING_TO_QUALITY: dict[ReviewRating, int] = {
    ReviewRating.again: 0,
    ReviewRating.hard: 3,
    ReviewRating.good: 4,
    ReviewRating.easy: 5,
}


class ReviewRequest(BaseModel):
    card_id: uuid.UUID
    rating: ReviewRating


class CardProgressResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    card_id: uuid.UUID
    ease_factor: float
    interval: int
    repetitions: int
    next_review_date: datetime
    last_reviewed_at: datetime | None
    total_reviews: int
    correct_reviews: int

    model_config = {"from_attributes": True}


class StudyCardResponse(BaseModel):
    id: uuid.UUID
    card_set_id: uuid.UUID
    front_text: str
    back_text: str
    example_sentence: str | None
    image_url: str | None
    audio_url: str | None
    card_type: CardType
    order_index: int
    created_at: datetime
    progress: CardProgressResponse | None = None

    model_config = {"from_attributes": True}


class AchievementUnlock(BaseModel):
    id: uuid.UUID
    title: str
    xp_reward: int


class ReviewResponse(BaseModel):
    card_id: uuid.UUID
    ease_factor: float
    interval: int
    next_review_date: datetime
    is_correct: bool
    xp_earned: int = 0
    new_achievements: list[AchievementUnlock] = []


class StudySetProgressResponse(BaseModel):
    total_cards: int
    learned_cards: int
    due_cards: int
    mastered_cards: int
