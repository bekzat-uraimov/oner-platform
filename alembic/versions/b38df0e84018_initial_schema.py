"""initial schema

Revision ID: b38df0e84018
Revises:
Create Date: 2026-06-25 08:45:55.102540

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b38df0e84018'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Enum types are created/dropped explicitly. `create_type=False` stops each
# create_table from re-issuing CREATE TYPE — `currency` is shared by two tables,
# so the auto-generated version double-creates it and fails on Postgres.
currency = postgresql.ENUM('KGS', 'KZT', 'UZS', 'USD', name='currency', create_type=False)
coursestatus = postgresql.ENUM('draft', 'published', name='coursestatus', create_type=False)
userrole = postgresql.ENUM('student', 'admin', name='userrole', create_type=False)
gateway = postgresql.ENUM('freedompay', 'manual', name='gateway', create_type=False)
purchasestatus = postgresql.ENUM('pending', 'paid', 'failed', name='purchasestatus', create_type=False)
materialtype = postgresql.ENUM('pdf', 'zip', 'link', 'other', name='materialtype', create_type=False)

_ALL_ENUMS = (currency, coursestatus, userrole, gateway, purchasestatus, materialtype)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in _ALL_ENUMS:
        enum.create(bind, checkfirst=True)

    op.create_table('courses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('slug', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('segment', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('currency', currency, nullable=False),
    sa.Column('status', coursestatus, nullable=False),
    sa.Column('cover', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_courses_slug'), 'courses', ['slug'], unique=True)
    op.create_index(op.f('ix_courses_status'), 'courses', ['status'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sqlmodel.sql.sqltypes.AutoString(length=320), nullable=False),
    sa.Column('password_hash', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('role', userrole, nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('modules',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('order', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_modules_course_id'), 'modules', ['course_id'], unique=False)
    op.create_table('price_audit',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('old_price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('new_price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('changed_by', sa.Integer(), nullable=False),
    sa.Column('changed_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['changed_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_price_audit_course_id'), 'price_audit', ['course_id'], unique=False)
    op.create_table('purchases',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('gateway', gateway, nullable=False),
    sa.Column('gateway_txn_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('currency', currency, nullable=False),
    sa.Column('status', purchasestatus, nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_purchases_course_id'), 'purchases', ['course_id'], unique=False)
    op.create_index(op.f('ix_purchases_gateway_txn_id'), 'purchases', ['gateway_txn_id'], unique=True)
    op.create_index(op.f('ix_purchases_status'), 'purchases', ['status'], unique=False)
    op.create_index(op.f('ix_purchases_user_id'), 'purchases', ['user_id'], unique=False)
    op.create_table('entitlements',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('granted_at', sa.DateTime(), nullable=False),
    sa.Column('source_purchase_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
    sa.ForeignKeyConstraint(['source_purchase_id'], ['purchases.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'course_id', name='uq_entitlement_user_course')
    )
    op.create_index(op.f('ix_entitlements_course_id'), 'entitlements', ['course_id'], unique=False)
    op.create_index(op.f('ix_entitlements_user_id'), 'entitlements', ['user_id'], unique=False)
    op.create_table('lessons',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('module_id', sa.Integer(), nullable=False),
    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('order', sa.Integer(), nullable=False),
    sa.Column('kinescope_video_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('duration', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['module_id'], ['modules.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_lessons_module_id'), 'lessons', ['module_id'], unique=False)
    op.create_table('materials',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('lesson_id', sa.Integer(), nullable=True),
    sa.Column('course_id', sa.Integer(), nullable=True),
    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('storage_key', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('type', materialtype, nullable=False),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
    sa.ForeignKeyConstraint(['lesson_id'], ['lessons.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_materials_course_id'), 'materials', ['course_id'], unique=False)
    op.create_index(op.f('ix_materials_lesson_id'), 'materials', ['lesson_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_materials_lesson_id'), table_name='materials')
    op.drop_index(op.f('ix_materials_course_id'), table_name='materials')
    op.drop_table('materials')
    op.drop_index(op.f('ix_lessons_module_id'), table_name='lessons')
    op.drop_table('lessons')
    op.drop_index(op.f('ix_entitlements_user_id'), table_name='entitlements')
    op.drop_index(op.f('ix_entitlements_course_id'), table_name='entitlements')
    op.drop_table('entitlements')
    op.drop_index(op.f('ix_purchases_user_id'), table_name='purchases')
    op.drop_index(op.f('ix_purchases_status'), table_name='purchases')
    op.drop_index(op.f('ix_purchases_gateway_txn_id'), table_name='purchases')
    op.drop_index(op.f('ix_purchases_course_id'), table_name='purchases')
    op.drop_table('purchases')
    op.drop_index(op.f('ix_price_audit_course_id'), table_name='price_audit')
    op.drop_table('price_audit')
    op.drop_index(op.f('ix_modules_course_id'), table_name='modules')
    op.drop_table('modules')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_courses_status'), table_name='courses')
    op.drop_index(op.f('ix_courses_slug'), table_name='courses')
    op.drop_table('courses')

    bind = op.get_bind()
    for enum in _ALL_ENUMS:
        enum.drop(bind, checkfirst=True)
