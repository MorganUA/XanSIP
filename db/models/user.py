import enum
from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, ForeignKey,
    Integer, String, Text, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base


class UserRole(str, enum.Enum):
    user = "user"
    support = "support"
    admin = "admin"
    superadmin = "superadmin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    internal_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.user, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    ban_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    banned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    banned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sip_accounts: Mapped[list["SipAccount"]] = relationship(
        back_populates="user",
        foreign_keys="[SipAccount.user_id]",
        lazy="selectin",
    )
    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="user",
        foreign_keys="[Ticket.user_id]",
        lazy="selectin",
    )
