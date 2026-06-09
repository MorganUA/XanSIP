import enum
from datetime import datetime
from sqlalchemy import (
    DateTime, Enum, ForeignKey, Integer, String, Text, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base


class SipStatus(str, enum.Enum):
    active = "active"
    frozen = "frozen"
    disabled = "disabled"


class SipAccount(Base):
    __tablename__ = "sip_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    sip_number: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[SipStatus] = mapped_column(
        Enum(SipStatus), default=SipStatus.active, nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Явно указываем foreign_keys чтобы SQLAlchemy не путался
    user: Mapped["User"] = relationship(
        back_populates="sip_accounts",
        foreign_keys=[user_id],
    )
    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="sip",
        foreign_keys="Ticket.sip_id",
    )
