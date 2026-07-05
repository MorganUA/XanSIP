"""SIP softphone credentials + call audit log.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sip_accounts", sa.Column("auth_username", sa.String(length=120), nullable=True))
    op.add_column("sip_accounts", sa.Column("auth_secret_enc", sa.String(length=512), nullable=True))

    op.create_table(
        "sip_call_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("sip_id", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("remote_number", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["sip_id"], ["sip_accounts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sip_call_logs_user_started", "sip_call_logs", ["user_id", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_sip_call_logs_user_started", table_name="sip_call_logs")
    op.drop_table("sip_call_logs")
    op.drop_column("sip_accounts", "auth_secret_enc")
    op.drop_column("sip_accounts", "auth_username")
