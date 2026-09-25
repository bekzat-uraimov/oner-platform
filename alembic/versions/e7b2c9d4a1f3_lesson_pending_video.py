"""lessons.pending_video_id

An upload still processing on Kinescope. It replaces kinescope_video_id only
once Kinescope reports it done, so a lesson never goes dark mid-replacement.
Indexed because Kinescope's status webhook looks lessons up by it.

Revision ID: e7b2c9d4a1f3
Revises: d4f8a1c2e6b7
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op


revision: str = 'e7b2c9d4a1f3'
down_revision: Union[str, Sequence[str], None] = 'd4f8a1c2e6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('lessons', sa.Column('pending_video_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.create_index(op.f('ix_lessons_pending_video_id'), 'lessons', ['pending_video_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_lessons_pending_video_id'), table_name='lessons')
    op.drop_column('lessons', 'pending_video_id')
