"""index lessons.kinescope_video_id

The DRM authorization callback looks a lesson up by video id on every playback
attempt, which makes this the hottest read in the app.

Revision ID: c1a7f4e9d2b3
Revises: b38df0e84018
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c1a7f4e9d2b3'
down_revision: Union[str, Sequence[str], None] = 'b38df0e84018'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        op.f('ix_lessons_kinescope_video_id'),
        'lessons',
        ['kinescope_video_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_lessons_kinescope_video_id'), table_name='lessons')
