from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_group_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    group_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    call_center_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    ban_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_frozen: Mapped[bool] = mapped_column(Boolean, default=False)
    frozen_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tariff: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tariff_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    participants_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    owner: Mapped["User | None"] = relationship(foreign_keys=[owner_user_id])
