import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import LanguageLevel


class CardType(str, enum.Enum):
    flashcard = "flashcard"
    fill_blank = "fill_blank"
    match = "match"
    listening = "listening"
    multiple_choice = "multiple_choice"
    sentence_build = "sentence_build"
    visual = "visual"


class CardSet(Base):
    __tablename__ = "card_sets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    difficulty_level: Mapped[LanguageLevel] = mapped_column(
        Enum(LanguageLevel, name="language_level_enum", create_type=False),
        nullable=False,
        default=LanguageLevel.A1,
    )
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_ai_generated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    card_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="card_sets")
    cards: Mapped[list["Card"]] = relationship(
        "Card", back_populates="card_set", cascade="all, delete-orphan"
    )


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    card_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("card_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    front_text: Mapped[str] = mapped_column(String(500), nullable=False)
    back_text: Mapped[str] = mapped_column(String(500), nullable=False)
    example_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    audio_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    card_type: Mapped[CardType] = mapped_column(
        Enum(CardType, name="card_type_enum"),
        nullable=False,
        default=CardType.flashcard,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    card_set: Mapped["CardSet"] = relationship("CardSet", back_populates="cards")
    progress: Mapped[list["UserCardProgress"]] = relationship(
        "UserCardProgress", back_populates="card", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_cards_card_set_id", "card_set_id"),
    )
