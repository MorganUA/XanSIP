"""service_desk_ticket_fields

Revision ID: a1b2c3d4e5f6
Revises: 77896774ce40
Create Date: 2026-06-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "77896774ce40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE ticketstatus ADD VALUE IF NOT EXISTS 'closed'")

    op.add_column("tickets", sa.Column("initiator_telegram_id", sa.BigInteger(), nullable=True))
    op.add_column("tickets", sa.Column("error_preset_id", sa.String(length=50), nullable=True))
    op.add_column("tickets", sa.Column("sip_number_snapshot", sa.String(length=50), nullable=True))
    op.add_column(
        "tickets",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("tickets", "updated_at")
    op.drop_column("tickets", "sip_number_snapshot")
    op.drop_column("tickets", "error_preset_id")
    op.drop_column("tickets", "initiator_telegram_id")
    # PostgreSQL does not support removing enum values safely; 'closed' remains.
