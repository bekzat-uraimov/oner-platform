"""lowercase emails, UTC timestamps, one open order per price

Emails are compared lowercased from now on, so existing ones are lowercased too.
Timestamps become timestamptz: the naive columns held UTC converted into the
server's zone, and returned without an offset. And a partial unique index keeps
a buyer to one pending order per course and price.

Revision ID: a4e9c1d7b3f2
Revises: f3c8a2d5b9e1
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'a4e9c1d7b3f2'
down_revision: Union[str, Sequence[str], None] = 'f3c8a2d5b9e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column, nullable)
TIMESTAMPS = [
    ('users', 'created_at', False),
    ('purchases', 'created_at', False),
    ('purchases', 'refunded_at', True),
    ('entitlements', 'granted_at', False),
    ('price_audit', 'changed_at', False),
]

OPEN_ORDER_COLUMNS = ['user_id', 'course_id', 'amount', 'currency']
OPEN_ORDER_WHERE = sa.text("status = 'pending'")


def _retype(*, timezone: bool) -> None:
    for table, column, nullable in TIMESTAMPS:
        op.alter_column(
            table,
            column,
            type_=sa.DateTime(timezone=timezone),
            existing_type=sa.DateTime(timezone=not timezone),
            existing_nullable=nullable,
            # The app wrote aware UTC values, which Postgres stored converted
            # into the session's zone. Reading them in that same zone recovers
            # the real instant, and the reverse works for the downgrade.
            postgresql_using=f"{column} AT TIME ZONE current_setting('TimeZone')",
        )


def upgrade() -> None:
    bind = op.get_bind()

    # Checked before changing anything, so a refusal leaves the database as it was.
    clashes = bind.execute(sa.text(
        "SELECT lower(trim(email)) FROM users GROUP BY lower(trim(email)) HAVING count(*) > 1"
    )).scalars().all()
    if clashes:
        raise RuntimeError(
            f"accounts differ only by email case: {', '.join(clashes)}. "
            "Rename or merge them, then run the migration again."
        )
    open_duplicates = bind.execute(sa.text(
        "SELECT count(*) FROM (SELECT 1 FROM purchases WHERE status = 'pending' "
        "GROUP BY user_id, course_id, amount, currency HAVING count(*) > 1) d"
    )).scalar()
    if open_duplicates:
        raise RuntimeError(
            f"{open_duplicates} buyers have duplicate pending orders at one price. "
            "Mark the older ones failed, then run the migration again."
        )

    op.execute("UPDATE users SET email = lower(trim(email)) WHERE email <> lower(trim(email))")
    _retype(timezone=True)
    op.create_index(
        'uq_pending_purchase', 'purchases', OPEN_ORDER_COLUMNS,
        unique=True, postgresql_where=OPEN_ORDER_WHERE,
    )


def downgrade() -> None:
    op.drop_index('uq_pending_purchase', table_name='purchases', postgresql_where=OPEN_ORDER_WHERE)
    _retype(timezone=False)
    # Emails stay lowercase: the case they were typed in isn't recorded anywhere.
