"""add xp_events table

Revision ID: a1b2c3d4e5f6
Revises: 3028de92ecf6
Create Date: 2026-02-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '3028de92ecf6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add xp_events table for tracking XP awards."""
    xp_event_type_enum = postgresql.ENUM(
        'review', 'set_created', 'ai_generation', 'achievement_bonus',
        name='xp_event_type_enum',
        create_type=False,
    )
    xp_event_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'xp_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('xp_amount', sa.Integer(), nullable=False),
        sa.Column('event_type', xp_event_type_enum, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_xp_events_user_created', 'xp_events', ['user_id', 'created_at'])


def downgrade() -> None:
    """Remove xp_events table."""
    op.drop_index('ix_xp_events_user_created', table_name='xp_events')
    op.drop_table('xp_events')
    sa.Enum(name='xp_event_type_enum').drop(op.get_bind(), checkfirst=True)
