"""add conversation to xp_event_type_enum

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-02-18 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add 'conversation' value to xp_event_type_enum."""
    op.execute("ALTER TYPE xp_event_type_enum ADD VALUE IF NOT EXISTS 'conversation'")


def downgrade() -> None:
    """PostgreSQL does not support removing enum values. No-op."""
    pass
