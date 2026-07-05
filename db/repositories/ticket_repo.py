from datetime import datetime, timezone
from sqlalchemy import select, and_, func, case, cast, Date
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

    async def get_with_details(self, ticket_id: int) -> Ticket | None:
        from sqlalchemy.orm import selectinload

        result = await self.session.execute(
            select(Ticket)
            .options(
                selectinload(Ticket.user),
                selectinload(Ticket.sip),
                selectinload(Ticket.status_history),
            )
            .where(Ticket.id == ticket_id)
        )
        return result.scalar_one_or_none()

    async def get_open_by_sip(self, sip_id: int) -> Ticket | None:
        """Проверяем есть ли уже незакрытый тикет по этому SIP."""
        result = await self.session.execute(
            select(Ticket).where(
                and_(
                    Ticket.sip_id == sip_id,
                    Ticket.status.in_([
                        TicketStatus.new,
                        TicketStatus.in_progress,
                        TicketStatus.waiting_info,
                    ]),
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: int, limit: int = 10) -> list[Ticket]:
        from sqlalchemy.orm import selectinload

        result = await self.session.execute(
            select(Ticket)
            .options(selectinload(Ticket.sip))
            .where(Ticket.user_id == user_id)
            .order_by(Ticket.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_active_by_group(self, group_id: int, *, limit: int = 20) -> list[Ticket]:
        from sqlalchemy.orm import selectinload

        result = await self.session.execute(
            select(Ticket)
            .options(selectinload(Ticket.sip))
            .where(
                Ticket.group_id == group_id,
                Ticket.status.in_([
                    TicketStatus.new,
                    TicketStatus.in_progress,
                    TicketStatus.waiting_info,
                ]),
            )
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

    async def list_recent(
        self,
        *,
        limit: int = 100,
        status: TicketStatus | None = None,
    ) -> list[Ticket]:
        from sqlalchemy.orm import selectinload

        query = (
            select(Ticket)
            .options(selectinload(Ticket.user), selectinload(Ticket.sip))
            .order_by(Ticket.created_at.desc())
            .limit(limit)
        )
        if status:
            query = query.where(Ticket.status == status)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_by_status(self) -> dict[str, int]:
        from sqlalchemy import func

        result = await self.session.execute(
            select(Ticket.status, func.count())
            .group_by(Ticket.status)
        )
        return {row[0].value: row[1] for row in result.all()}

    async def count_open_grouped_by_sip(self) -> dict[int, int]:
        open_statuses = [
            TicketStatus.new,
            TicketStatus.in_progress,
            TicketStatus.waiting_info,
        ]
        result = await self.session.execute(
            select(Ticket.sip_id, func.count())
            .where(
                Ticket.sip_id.isnot(None),
                Ticket.status.in_(open_statuses),
            )
            .group_by(Ticket.sip_id)
        )
        return {int(row[0]): int(row[1]) for row in result.all()}

    async def count_active_by_user(self, user_id: int) -> int:
        open_statuses = [
            TicketStatus.new,
            TicketStatus.in_progress,
            TicketStatus.waiting_info,
        ]
        result = await self.session.execute(
            select(func.count())
            .select_from(Ticket)
            .where(Ticket.user_id == user_id, Ticket.status.in_(open_statuses))
        )
        return int(result.scalar_one())

    async def first_open_ticket_id_by_sip_ids(self, sip_ids: list[int]) -> dict[int, int]:
        if not sip_ids:
            return {}
        open_statuses = [
            TicketStatus.new,
            TicketStatus.in_progress,
            TicketStatus.waiting_info,
        ]
        result = await self.session.execute(
            select(Ticket.sip_id, Ticket.id)
            .where(Ticket.sip_id.in_(sip_ids), Ticket.status.in_(open_statuses))
            .order_by(Ticket.sip_id, Ticket.created_at.desc())
        )
        out: dict[int, int] = {}
        for sip_id, ticket_id in result.all():
            if sip_id is not None and sip_id not in out:
                out[int(sip_id)] = int(ticket_id)
        return out

    async def count_created_since(self, since: datetime) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Ticket).where(Ticket.created_at >= since)
        )
        return int(result.scalar_one())

    async def count_resolved_since(self, since: datetime) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Ticket).where(
                Ticket.resolved_at.isnot(None),
                Ticket.resolved_at >= since,
            )
        )
        return int(result.scalar_one())

    async def avg_resolution_seconds_since(self, since: datetime) -> float | None:
        result = await self.session.execute(
            select(
                func.avg(
                    func.extract("epoch", Ticket.resolved_at - Ticket.created_at)
                )
            ).where(
                Ticket.resolved_at.isnot(None),
                Ticket.resolved_at >= since,
            )
        )
        val = result.scalar_one()
        return float(val) if val is not None else None

    async def count_by_error_type_since(self, since: datetime) -> dict[str, int]:
        result = await self.session.execute(
            select(Ticket.error_type, func.count())
            .where(Ticket.created_at >= since)
            .group_by(Ticket.error_type)
        )
        return {row[0].value: row[1] for row in result.all()}

    async def count_by_source_since(self, since: datetime) -> dict[str, int]:
        result = await self.session.execute(
            select(Ticket.source, func.count())
            .where(Ticket.created_at >= since)
            .group_by(Ticket.source)
        )
        return {row[0].value: row[1] for row in result.all()}

    async def top_sips_since(self, since: datetime, *, limit: int = 15) -> list[dict]:
        open_statuses = [
            TicketStatus.new,
            TicketStatus.in_progress,
            TicketStatus.waiting_info,
        ]
        sip_expr = func.coalesce(Ticket.sip_number_snapshot, "—")
        result = await self.session.execute(
            select(
                sip_expr.label("sip_number"),
                func.count().label("total"),
                func.sum(
                    case((Ticket.status.in_(open_statuses), 1), else_=0)
                ).label("open"),
            )
            .where(Ticket.created_at >= since)
            .group_by(sip_expr)
            .order_by(func.count().desc())
            .limit(limit)
        )
        return [
            {
                "sip_number": row.sip_number,
                "total": int(row.total),
                "open": int(row.open or 0),
            }
            for row in result.all()
        ]

    async def sips_with_open_tickets(self, *, limit: int = 15) -> list[dict]:
        open_statuses = [
            TicketStatus.new,
            TicketStatus.in_progress,
            TicketStatus.waiting_info,
        ]
        sip_expr = func.coalesce(Ticket.sip_number_snapshot, "—")
        result = await self.session.execute(
            select(
                sip_expr.label("sip_number"),
                func.count().label("open"),
            )
            .where(Ticket.status.in_(open_statuses))
            .group_by(sip_expr)
            .order_by(func.count().desc())
            .limit(limit)
        )
        return [
            {"sip_number": row.sip_number, "open": int(row.open)}
            for row in result.all()
        ]

    async def agent_stats_since(self, since: datetime, *, limit: int = 10) -> list[dict]:
        result = await self.session.execute(
            select(
                Ticket.assigned_to.label("user_id"),
                func.count().label("taken"),
                func.sum(
                    case((Ticket.status == TicketStatus.resolved, 1), else_=0)
                ).label("resolved"),
            )
            .where(
                Ticket.assigned_to.isnot(None),
                Ticket.created_at >= since,
            )
            .group_by(Ticket.assigned_to)
            .order_by(func.count().desc())
            .limit(limit)
        )
        return [
            {
                "user_id": row.user_id,
                "taken": int(row.taken),
                "resolved": int(row.resolved or 0),
            }
            for row in result.all()
        ]

    async def daily_counts_since(self, since: datetime) -> list[dict]:
        day = cast(Ticket.created_at, Date)
        created_q = (
            select(day.label("d"), func.count().label("created"))
            .where(Ticket.created_at >= since)
            .group_by(day)
        )
        created_map: dict[str, int] = {}
        for row in (await self.session.execute(created_q)).all():
            created_map[str(row.d)] = int(row.created)

        res_day = cast(Ticket.resolved_at, Date)
        resolved_q = (
            select(res_day.label("d"), func.count().label("resolved"))
            .where(
                Ticket.resolved_at.isnot(None),
                Ticket.resolved_at >= since,
            )
            .group_by(res_day)
        )
        resolved_map: dict[str, int] = {}
        for row in (await self.session.execute(resolved_q)).all():
            resolved_map[str(row.d)] = int(row.resolved)

        all_days = sorted(set(created_map) | set(resolved_map))
        return [
            {
                "date": d,
                "created": created_map.get(d, 0),
                "resolved": resolved_map.get(d, 0),
            }
            for d in all_days
        ]

    async def list_active_service_desk(self, *, limit: int = 100) -> list[Ticket]:
        from sqlalchemy.orm import selectinload

        result = await self.session.execute(
            select(Ticket)
            .options(selectinload(Ticket.user), selectinload(Ticket.sip))
            .where(
                Ticket.status.in_([
                    TicketStatus.new,
                    TicketStatus.in_progress,
                    TicketStatus.waiting_info,
                ]),
                Ticket.source == TicketSource.group_chat,
            )
            .order_by(Ticket.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create_service_desk(
        self,
        *,
        user_id: int,
        sip_id: int,
        group_id: int,
        error_type: ErrorType,
        description: str,
        initiator_telegram_id: int,
        error_preset_id: str,
        sip_number_snapshot: str,
    ) -> Ticket:
        ticket = Ticket(
            user_id=user_id,
            sip_id=sip_id,
            group_id=group_id,
            error_type=error_type,
            description=description,
            source=TicketSource.group_chat,
            initiator_telegram_id=initiator_telegram_id,
            error_preset_id=error_preset_id,
            sip_number_snapshot=sip_number_snapshot,
            status=TicketStatus.new,
        )
        self.session.add(ticket)
        await self.session.commit()
        await self.session.refresh(ticket)
        return ticket

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
