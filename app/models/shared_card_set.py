import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SharedCardSet(Base):
    __tablename__ = "shared_card_sets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    card_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("card_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    shared_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    shared_with_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    card_set: Mapped["CardSet"] = relationship("CardSet")
    shared_by: Mapped["User"] = relationship("User", foreign_keys=[shared_by_id])
    shared_with: Mapped["User"] = relationship("User", foreign_keys=[shared_with_id])

    __table_args__ = (
        UniqueConstraint(
            "card_set_id", "shared_with_id", name="uq_shared_card_set_recipient"
        ),
    )
