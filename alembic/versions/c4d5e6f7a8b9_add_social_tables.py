"""add social tables

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-02-18 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add UniqueConstraint and indexes to friendships table
    op.create_unique_constraint('uq_friendship_pair', 'friendships', ['user_id', 'friend_id'])
    op.create_index('ix_friendships_user_id', 'friendships', ['user_id'])
    op.create_index('ix_friendships_friend_id', 'friendships', ['friend_id'])

    # Create shared_card_sets table
    op.create_table(
        'shared_card_sets',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('card_set_id', sa.UUID(), nullable=False),
        sa.Column('shared_by_id', sa.UUID(), nullable=False),
        sa.Column('shared_with_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['card_set_id'], ['card_sets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shared_by_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shared_with_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('card_set_id', 'shared_with_id', name='uq_shared_card_set_recipient'),
    )

    # Add new enum values
    op.execute("ALTER TYPE xp_event_type_enum ADD VALUE IF NOT EXISTS 'friend_added'")
    op.execute("ALTER TYPE achievement_condition_enum ADD VALUE IF NOT EXISTS 'friends_count'")


def downgrade() -> None:
    op.drop_table('shared_card_sets')
    op.drop_index('ix_friendships_friend_id', table_name='friendships')
    op.drop_index('ix_friendships_user_id', table_name='friendships')
    op.drop_constraint('uq_friendship_pair', 'friendships', type_='unique')
