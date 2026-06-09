from datetime import datetime, timezone
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.ticket import (
    Ticket, TicketStatus, TicketStatusHistory,
    TicketComment, ErrorType, TicketSource
)


class TicketRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, ticket_id: int) -> Ticket | None:
        result = await self.session.execute(
            select(Ticket).where(Ticket.id == ticket_id)
        )
        return result.scalar_one_or_none()

    async def get_open_by_sip(self, sip_id: int) -> Ticket | None:
        """Проверяем есть ли уже открытый тикет по этому SIP."""
        result = await self.session.execute(
            select(Ticket).where(
                and_(
                    Ticket.sip_id == sip_id,
                    Ticket.status.in_([TicketStatus.new, TicketStatus.in_progress]),
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: int, limit: int = 10) -> list[Ticket]:
        result = await self.session.execute(
            select(Ticket)
            .where(Ticket.user_id == user_id)
            .order_by(Ticket.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_all_open(self) -> list[Ticket]:
        result = await self.session.execute(
            select(Ticket)
            .where(Ticket.status.in_([TicketStatus.new, TicketStatus.in_progress]))
            .order_by(Ticket.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(
        self,
        user_id: int,
        error_type: ErrorType,
        description: str,
        sip_id: int | None = None,
        group_id: int | None = None,
        source: TicketSource = TicketSource.personal_chat,
    ) -> Ticket:
        ticket = Ticket(
            user_id=user_id,
            sip_id=sip_id,
            group_id=group_id,
            error_type=error_type,
            description=description,
            source=source,
        )
        self.session.add(ticket)
        await self.session.commit()
        await self.session.refresh(ticket)
        return ticket

    async def update_status(
        self,
        ticket: Ticket,
        new_status: TicketStatus,
        changed_by_id: int | None = None,
        comment: str | None = None,
    ) -> Ticket:
        old_status = ticket.status.value

        # Если решено — ставим время решения
        if new_status == TicketStatus.resolved:
            ticket.resolved_at = datetime.now(timezone.utc)

        ticket.status = new_status

        # Пишем в историю
        history = TicketStatusHistory(
            ticket_id=ticket.id,
            old_status=old_status,
            new_status=new_status.value,
            changed_by=changed_by_id,
            comment=comment,
        )
        self.session.add(history)
        await self.session.commit()
        await self.session.refresh(ticket)
        return ticket

    async def assign(self, ticket: Ticket, agent_id: int) -> Ticket:
        ticket.assigned_to = agent_id
        await self.session.commit()
        return ticket

    async def set_support_message_id(
        self, ticket: Ticket, message_id: int
    ) -> Ticket:
        ticket.support_message_id = message_id
        await self.session.commit()
        return ticket

    async def add_comment(
        self,
        ticket_id: int,
        author_id: int,
        text: str,
        is_internal: bool = False,
    ) -> TicketComment:
        comment = TicketComment(
            ticket_id=ticket_id,
            author_id=author_id,
            text=text,
            is_internal=is_internal,
        )
        self.session.add(comment)
        await self.session.commit()
        return comment
