import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class League(str, enum.Enum):
    Bronze = "Bronze"
    Silver = "Silver"
    Gold = "Gold"
    Platinum = "Platinum"
    Diamond = "Diamond"


class XpEventType(str, enum.Enum):
    review = "review"
    set_created = "set_created"
    ai_generation = "ai_generation"
    conversation = "conversation"
    achievement_bonus = "achievement_bonus"
    friend_added = "friend_added"


class AchievementCondition(str, enum.Enum):
    cards_learned = "cards_learned"
    streak_days = "streak_days"
    conversations = "conversations"
    xp_earned = "xp_earned"
    sets_created = "sets_created"
    perfect_reviews = "perfect_reviews"
    friends_count = "friends_count"


class UserGamification(Base):
    __tablename__ = "user_gamification"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    total_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_activity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    league: Mapped[League] = mapped_column(
        Enum(League, name="league_enum"),
        nullable=False,
        default=League.Bronze,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="gamification")

    __table_args__ = (
        Index("ix_user_gamification_league_xp", "league", "total_xp"),
    )


class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    icon_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    condition_type: Mapped[AchievementCondition] = mapped_column(
        Enum(AchievementCondition, name="achievement_condition_enum"),
        nullable=False,
    )
    condition_value: Mapped[int] = mapped_column(Integer, nullable=False)
    xp_reward: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    achievement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("achievements.id", ondelete="CASCADE"),
        nullable=False,
    )
    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="achievements")
    achievement: Mapped["Achievement"] = relationship("Achievement")

    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
    )


class XpEvent(Base):
    __tablename__ = "xp_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    xp_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[XpEventType] = mapped_column(
        Enum(XpEventType, name="xp_event_type_enum"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="xp_events")

    __table_args__ = (
        Index("ix_xp_events_user_created", "user_id", "created_at"),
    )
