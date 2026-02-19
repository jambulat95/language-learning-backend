import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FriendshipStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"


class Friendship(Base):
    __tablename__ = "friendships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    friend_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[FriendshipStatus] = mapped_column(
        Enum(FriendshipStatus, name="friendship_status_enum"),
        nullable=False,
        default=FriendshipStatus.pending,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User", foreign_keys=[user_id], backref="friendships_sent"
    )
    friend: Mapped["User"] = relationship(
        "User", foreign_keys=[friend_id], backref="friendships_received"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "friend_id", name="uq_friendship_pair"),
        Index("ix_friendships_user_id", "user_id"),
        Index("ix_friendships_friend_id", "friend_id"),
    )
