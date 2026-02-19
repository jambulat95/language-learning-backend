import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.friendship import FriendshipStatus
from app.models.gamification import League
from app.models.user import LanguageLevel


# --- Friend Requests ---

class SendFriendRequestRequest(BaseModel):
    friend_id: uuid.UUID


class FriendUserInfo(BaseModel):
    id: uuid.UUID
    full_name: str
    avatar_url: str | None = None
    language_level: LanguageLevel

    model_config = {"from_attributes": True}


class FriendshipResponse(BaseModel):
    id: uuid.UUID
    user: FriendUserInfo
    status: FriendshipStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class FriendResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    avatar_url: str | None = None
    language_level: LanguageLevel
    is_premium: bool

    model_config = {"from_attributes": True}


# --- Card Set Sharing ---

class ShareCardSetRequest(BaseModel):
    friend_id: uuid.UUID


class SharedCardSetInfo(BaseModel):
    id: uuid.UUID
    title: str
    card_count: int
    difficulty_level: LanguageLevel

    model_config = {"from_attributes": True}


class SharedByInfo(BaseModel):
    id: uuid.UUID
    full_name: str
    avatar_url: str | None = None

    model_config = {"from_attributes": True}


class SharedCardSetResponse(BaseModel):
    id: uuid.UUID
    card_set: SharedCardSetInfo
    shared_by: SharedByInfo
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Friend Progress ---

class FriendGamificationStats(BaseModel):
    total_xp: int
    level: int
    league: League
    current_streak: int
    longest_streak: int


class FriendStudyStats(BaseModel):
    words_learned: int
    words_mastered: int
    study_days: int
    accuracy: float


class FriendProgressResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    avatar_url: str | None = None
    language_level: LanguageLevel
    is_premium: bool
    gamification: FriendGamificationStats
    study: FriendStudyStats

    model_config = {"from_attributes": True}


# --- User Search ---

class UserSearchResult(BaseModel):
    id: uuid.UUID
    full_name: str
    avatar_url: str | None = None
    language_level: LanguageLevel
    friendship_status: FriendshipStatus | None = None
    friendship_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}
