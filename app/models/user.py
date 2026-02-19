import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LanguageLevel(str, enum.Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    language_level: Mapped[LanguageLevel] = mapped_column(
        Enum(LanguageLevel, name="language_level_enum"),
        nullable=False,
        default=LanguageLevel.A1,
    )
    native_language: Mapped[str] = mapped_column(
        String(10), nullable=False, default="ru"
    )
    daily_xp_goal: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_premium: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    interests: Mapped[list["UserInterest"]] = relationship(
        "UserInterest", back_populates="user", cascade="all, delete-orphan"
    )
    card_sets: Mapped[list["CardSet"]] = relationship(
        "CardSet", back_populates="user", cascade="all, delete-orphan"
    )
    card_progress: Mapped[list["UserCardProgress"]] = relationship(
        "UserCardProgress", back_populates="user", cascade="all, delete-orphan"
    )
    gamification: Mapped["UserGamification | None"] = relationship(
        "UserGamification", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    achievements: Mapped[list["UserAchievement"]] = relationship(
        "UserAchievement", back_populates="user", cascade="all, delete-orphan"
    )
    xp_events: Mapped[list["XpEvent"]] = relationship(
        "XpEvent", back_populates="user", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["AIConversation"]] = relationship(
        "AIConversation", back_populates="user", cascade="all, delete-orphan"
    )
