import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.user import LanguageLevel


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    language_level: LanguageLevel
    is_premium: bool
    is_active: bool
    is_admin: bool
    created_at: datetime
    card_sets_count: int
    total_xp: int
    level: int
    league: str


class PaginatedAdminUserResponse(BaseModel):
    items: list[AdminUserResponse]
    total: int
    skip: int
    limit: int


class AdminUserUpdateRequest(BaseModel):
    is_premium: bool | None = None
    is_active: bool | None = None


class AdminCardSetResponse(BaseModel):
    id: uuid.UUID
    title: str
    user_email: str
    user_full_name: str
    difficulty_level: LanguageLevel
    card_count: int
    is_public: bool
    is_ai_generated: bool
    created_at: datetime


class PaginatedAdminCardSetResponse(BaseModel):
    items: list[AdminCardSetResponse]
    total: int
    skip: int
    limit: int


class PlatformStatsResponse(BaseModel):
    total_users: int
    premium_users: int
    total_card_sets: int
    public_card_sets: int
    total_cards: int
    total_conversations: int
    active_today: int
