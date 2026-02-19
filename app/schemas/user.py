import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.models.user import LanguageLevel

InterestType = Literal[
    "technology", "science", "travel", "food", "sports",
    "music", "movies", "books", "gaming", "art",
    "business", "health", "fashion", "nature", "history",
    "photography", "education", "politics", "humor", "pets",
]


# --- Auth requests ---

class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    native_language: str = Field(default="ru", max_length=10)
    language_level: LanguageLevel = LanguageLevel.A1
    interests: list[InterestType] = Field(min_length=3, max_length=10)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PasswordResetRequestSchema(BaseModel):
    email: EmailStr


class PasswordResetConfirmSchema(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


# --- User response/update ---

class InterestResponse(BaseModel):
    id: uuid.UUID
    interest: str

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    avatar_url: str | None
    language_level: LanguageLevel
    native_language: str
    daily_xp_goal: int
    is_premium: bool
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime | None
    interests: list[InterestResponse]

    model_config = {"from_attributes": True}


class UsageLimitsResponse(BaseModel):
    is_premium: bool
    card_sets_used: int
    card_sets_limit: int
    cards_today: int
    cards_today_limit: int
    ai_dialogues_used: int
    ai_dialogues_limit: int


class UserUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    avatar_url: str | None = None
    language_level: LanguageLevel | None = None
    native_language: str | None = Field(default=None, max_length=10)
    daily_xp_goal: int | None = Field(default=None, ge=10, le=1000)
    interests: list[InterestType] | None = Field(default=None, min_length=3, max_length=10)
