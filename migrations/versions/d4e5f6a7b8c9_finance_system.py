"""finance system: balances, USDT wallets, deposits, audit events

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

deposit_status = postgresql.ENUM(
    "pending", "awaiting_review", "confirmed", "rejected", "expired", "cancelled",
    name="depositstatus",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE depositstatus AS ENUM (
                'pending', 'awaiting_review', 'confirmed', 'rejected', 'expired', 'cancelled'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    if "user_accounts" not in existing:
        op.create_table(
            "user_accounts",
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
            sa.Column("balance_usdt", sa.Numeric(18, 6), server_default="0", nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if "usdt_wallets" not in existing:
        op.create_table(
            "usdt_wallets",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("address", sa.String(128), nullable=False),
            sa.Column("label", sa.String(120), nullable=True),
            sa.Column("network", sa.String(32), server_default="TRC20", nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_usdt_wallets_active", "usdt_wallets", ["is_active"])

    if "deposits" not in existing:
        op.create_table(
            "deposits",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("wallet_id", sa.Integer(), sa.ForeignKey("usdt_wallets.id"), nullable=False),
            sa.Column("amount_usdt", sa.Numeric(18, 6), nullable=False),
            sa.Column("status", deposit_status, server_default="pending", nullable=False),
            sa.Column("tx_hash", sa.String(128), nullable=True),
            sa.Column("admin_note", sa.Text(), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("confirmed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_deposits_user_status", "deposits", ["user_id", "status"])

    if "audit_events" not in existing:
        op.create_table(
            "audit_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("actor_label", sa.String(120), nullable=True),
            sa.Column("category", sa.String(50), nullable=False),
            sa.Column("action", sa.String(100), nullable=False),
            sa.Column("entity_type", sa.String(50), nullable=True),
            sa.Column("entity_id", sa.String(64), nullable=True),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_audit_events_created", "audit_events", ["created_at"])
        op.create_index("ix_audit_events_category", "audit_events", ["category"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("deposits")
    op.drop_table("usdt_wallets")
    op.drop_table("user_accounts")
    op.execute("DROP TYPE IF EXISTS depositstatus")
