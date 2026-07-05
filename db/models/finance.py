import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class DepositStatus(str, enum.Enum):
    pending = "pending"
    awaiting_review = "awaiting_review"
    confirmed = "confirmed"
    rejected = "rejected"
    expired = "expired"
    cancelled = "cancelled"


class UserAccount(Base):
    __tablename__ = "user_accounts"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    balance_usdt: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    user: Mapped["User"] = relationship(foreign_keys=[user_id])


class UsdtWallet(Base):
    __tablename__ = "usdt_wallets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    address: Mapped[str] = mapped_column(String(128), nullable=False)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    network: Mapped[str] = mapped_column(String(32), default="TRC20")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )


class Deposit(Base):
    __tablename__ = "deposits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("usdt_wallets.id"), nullable=False)
    amount_usdt: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    status: Mapped[DepositStatus] = mapped_column(
        Enum(DepositStatus), default=DepositStatus.pending,
    )
    tx_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    wallet: Mapped["UsdtWallet"] = relationship()
    confirmer: Mapped["User | None"] = relationship(foreign_keys=[confirmed_by])
