import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.card import CardType
from app.models.user import LanguageLevel


# --- CardSet schemas ---

class CardSetCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, max_length=100)
    difficulty_level: LanguageLevel = LanguageLevel.A1
    is_public: bool = False


class CardSetUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, max_length=100)
    difficulty_level: LanguageLevel | None = None
    is_public: bool | None = None


class CardResponse(BaseModel):
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

    model_config = {"from_attributes": True}


class CardSetResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: str | None
    category: str | None
    difficulty_level: LanguageLevel
    is_public: bool
    is_ai_generated: bool
    card_count: int
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class CardSetDetailResponse(CardSetResponse):
    cards: list[CardResponse] = []


# --- Card schemas ---

class CardCreate(BaseModel):
    front_text: str = Field(min_length=1, max_length=500)
    back_text: str = Field(min_length=1, max_length=500)
    example_sentence: str | None = None
    image_url: str | None = Field(default=None, max_length=512)
    audio_url: str | None = Field(default=None, max_length=512)
    card_type: CardType = CardType.flashcard
    order_index: int = 0


class CardUpdate(BaseModel):
    front_text: str | None = Field(default=None, min_length=1, max_length=500)
    back_text: str | None = Field(default=None, min_length=1, max_length=500)
    example_sentence: str | None = None
    image_url: str | None = Field(default=None, max_length=512)
    audio_url: str | None = Field(default=None, max_length=512)
    card_type: CardType | None = None
    order_index: int | None = None


# --- Pagination ---

class PaginatedCardSetResponse(BaseModel):
    items: list[CardSetResponse]
    total: int
    skip: int
    limit: int


class PaginatedCardResponse(BaseModel):
    items: list[CardResponse]
    total: int
    skip: int
    limit: int


# --- Bulk / Import ---

class CardBulkCreate(BaseModel):
    cards: list[CardCreate] = Field(min_length=1, max_length=500)


class CardBulkResponse(BaseModel):
    created_count: int
    cards: list[CardResponse]


class CardImportResponse(BaseModel):
    imported_count: int
    skipped_count: int
    cards: list[CardResponse]
