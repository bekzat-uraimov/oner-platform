"""purchase refunds

Adds 'refunded' to purchasestatus, and who recorded a refund, when, and why.
The money goes back through FreedomPay's merchant cabinet; these columns are
the record that it did.

Revision ID: f3c8a2d5b9e1
Revises: e7b2c9d4a1f3
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op


revision: str = 'f3c8a2d5b9e1'
down_revision: Union[str, Sequence[str], None] = 'e7b2c9d4a1f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Allowed inside a transaction since Postgres 12, as long as nothing in the
    # same transaction uses the new value.
    op.execute("ALTER TYPE purchasestatus ADD VALUE IF NOT EXISTS 'refunded'")
    op.add_column('purchases', sa.Column('refunded_at', sa.DateTime(), nullable=True))
    op.add_column('purchases', sa.Column('refunded_by', sa.Integer(), nullable=True))
    op.add_column('purchases', sa.Column('refund_note', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.create_foreign_key('purchases_refunded_by_fkey', 'purchases', 'users', ['refunded_by'], ['id'])


def downgrade() -> None:
    refunded = op.get_bind().execute(
        sa.text("SELECT count(*) FROM purchases WHERE status = 'refunded'")
    ).scalar()
    if refunded:
        # Postgres can't drop an enum value in use, and turning a refund back
        # into 'paid' would misstate money that was returned.
        raise RuntimeError(f"{refunded} refunded purchases would be lost; not downgrading")

    op.drop_constraint('purchases_refunded_by_fkey', 'purchases', type_='foreignkey')
    op.drop_column('purchases', 'refund_note')
    op.drop_column('purchases', 'refunded_by')
    op.drop_column('purchases', 'refunded_at')
    # Postgres has no DROP VALUE, so rebuild the type without it.
    op.execute("ALTER TYPE purchasestatus RENAME TO purchasestatus_old")
    op.execute("CREATE TYPE purchasestatus AS ENUM ('pending', 'paid', 'failed')")
    op.execute(
        "ALTER TABLE purchases ALTER COLUMN status TYPE purchasestatus "
        "USING status::text::purchasestatus"
    )
    op.execute("DROP TYPE purchasestatus_old")
