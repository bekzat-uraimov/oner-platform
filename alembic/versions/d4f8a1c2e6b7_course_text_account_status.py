"""course, module and lesson text; account status; one row per stored file

Adds the course page's "What you'll learn" and "Requirements", a description on
every module and lesson, users.is_active for disabling an account, and a unique
constraint on materials.storage_key so deleting a row can safely delete its R2
file.

Revision ID: d4f8a1c2e6b7
Revises: c1a7f4e9d2b3
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op


revision: str = 'd4f8a1c2e6b7'
down_revision: Union[str, Sequence[str], None] = 'c1a7f4e9d2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('courses', sa.Column('learning_outcomes', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('courses', sa.Column('requirements', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('modules', sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('lessons', sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    # The server default fills every existing account, so nobody is locked out.
    op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_unique_constraint('uq_material_storage_key', 'materials', ['storage_key'])


def downgrade() -> None:
    op.drop_constraint('uq_material_storage_key', 'materials', type_='unique')
    op.drop_column('users', 'is_active')
    op.drop_column('lessons', 'description')
    op.drop_column('modules', 'description')
    op.drop_column('courses', 'requirements')
    op.drop_column('courses', 'learning_outcomes')
