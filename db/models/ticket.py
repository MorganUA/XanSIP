import enum
from datetime import datetime
from sqlalchemy import (
    BigInteger, DateTime, Enum, ForeignKey,
    Integer, String, Text, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base


class ErrorType(str, enum.Enum):
    busy_here = "busy_here"
    no_registration = "no_registration"
    no_calls = "no_calls"
    no_balance = "no_balance"
    sim_problem = "sim_problem"
    other = "other"


class TicketStatus(str, enum.Enum):
    new = "new"
    in_progress = "in_progress"
    resolved = "resolved"
    rejected = "rejected"
    waiting_info = "waiting_info"
    closed = "closed"


class TicketSource(str, enum.Enum):
    personal_chat = "personal_chat"
    group_chat = "group_chat"
    command = "command"


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    sip_id: Mapped[int | None] = mapped_column(ForeignKey("sip_accounts.id"), nullable=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"), nullable=True)
    error_type: Mapped[ErrorType] = mapped_column(Enum(ErrorType), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus), default=TicketStatus.new, nullable=False
    )
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    source: Mapped[TicketSource] = mapped_column(
        Enum(TicketSource), default=TicketSource.personal_chat, nullable=False
    )
    support_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    initiator_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error_preset_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sip_number_snapshot: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(
        back_populates="tickets", foreign_keys=[user_id]
    )
    sip: Mapped["SipAccount | None"] = relationship(back_populates="tickets")
    status_history: Mapped[list["TicketStatusHistory"]] = relationship(
        back_populates="ticket", lazy="selectin"
    )
    comments: Mapped[list["TicketComment"]] = relationship(
        back_populates="ticket", lazy="selectin"
    )


class TicketStatusHistory(Base):
    __tablename__ = "ticket_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=False)
    old_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    ticket: Mapped["Ticket"] = relationship(back_populates="status_history")


class TicketComment(Base):
    __tablename__ = "ticket_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    ticket: Mapped["Ticket"] = relationship(back_populates="comments")
