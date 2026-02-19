from pydantic import BaseModel, Field

from app.models.user import LanguageLevel
from app.schemas.card import CardSetDetailResponse


class GenerateCardsRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    difficulty_level: LanguageLevel = LanguageLevel.A1
    count: int = Field(default=10, ge=5, le=30)
    interests: list[str] = Field(default_factory=list, max_length=10)


class GeneratedCardItem(BaseModel):
    front_text: str
    back_text: str
    example_sentence: str | None = None


class GenerateCardsResponse(BaseModel):
    card_set: CardSetDetailResponse
    generated_count: int
