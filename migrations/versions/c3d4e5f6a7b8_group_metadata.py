"""group metadata, freeze, soft delete

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("groups", sa.Column("call_center_label", sa.String(255), nullable=True))
    op.add_column("groups", sa.Column("tariff", sa.String(120), nullable=True))
    op.add_column("groups", sa.Column("tariff_notes", sa.Text(), nullable=True))
    op.add_column("groups", sa.Column("work_conditions", sa.Text(), nullable=True))
    op.add_column("groups", sa.Column("participants_info", sa.Text(), nullable=True))
    op.add_column("groups", sa.Column("contact_info", sa.Text(), nullable=True))
    op.add_column("groups", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("groups", sa.Column("is_frozen", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("groups", sa.Column("frozen_reason", sa.Text(), nullable=True))
    op.add_column("groups", sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("groups", sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("groups", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("groups", "deleted_at")
    op.drop_column("groups", "is_deleted")
    op.drop_column("groups", "frozen_at")
    op.drop_column("groups", "frozen_reason")
    op.drop_column("groups", "is_frozen")
    op.drop_column("groups", "notes")
    op.drop_column("groups", "contact_info")
    op.drop_column("groups", "participants_info")
    op.drop_column("groups", "work_conditions")
    op.drop_column("groups", "tariff_notes")
    op.drop_column("groups", "tariff")
    op.drop_column("groups", "call_center_label")
