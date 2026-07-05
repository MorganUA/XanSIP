from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.group import Group
from db.models.ticket import Ticket, TicketStatus


class GroupRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def restore_deleted(
        self,
        group: Group,
        *,
        group_name: str | None = None,
        owner_user_id: int | None = None,
    ) -> Group:
        group.is_deleted = False
        group.deleted_at = None
        group.is_approved = False
        group.is_banned = False
        group.is_frozen = False
        group.ban_reason = None
        group.frozen_reason = None
        group.frozen_at = None
        if group_name is not None:
            group.group_name = group_name
        if owner_user_id is not None:
            group.owner_user_id = owner_user_id
        await self.session.commit()
        await self.session.refresh(group)
        return group

    async def get_by_telegram_id_any(self, telegram_group_id: int) -> Group | None:
        result = await self.session.execute(
            select(Group).where(Group.telegram_group_id == telegram_group_id)
        )
        return result.scalar_one_or_none()

    async def get_by_telegram_id(self, telegram_group_id: int) -> Group | None:
        result = await self.session.execute(
            select(Group).where(
                Group.telegram_group_id == telegram_group_id,
                Group.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, group_id: int, *, include_deleted: bool = False) -> Group | None:
        query = select(Group).where(Group.id == group_id)
        if not include_deleted:
            query = query.where(Group.is_deleted.is_(False))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create(
        self,
        telegram_group_id: int,
        group_name: str | None = None,
        owner_user_id: int | None = None,
        *,
        call_center_label: str | None = None,
        tariff: str | None = None,
        tariff_notes: str | None = None,
        work_conditions: str | None = None,
        participants_info: str | None = None,
        contact_info: str | None = None,
        notes: str | None = None,
        is_approved: bool = False,
    ) -> Group:
        group = Group(
            telegram_group_id=telegram_group_id,
            group_name=group_name,
            owner_user_id=owner_user_id,
            call_center_label=call_center_label,
            tariff=tariff,
            tariff_notes=tariff_notes,
            work_conditions=work_conditions,
            participants_info=participants_info,
            contact_info=contact_info,
            notes=notes,
            is_approved=is_approved,
        )
        self.session.add(group)
        await self.session.commit()
        await self.session.refresh(group)
        return group

    async def approve(self, group: Group, approved_by_id: int) -> Group:
        group.is_approved = True
        group.approved_by = approved_by_id
        group.approved_at = datetime.now(timezone.utc)
        await self.session.commit()
        return group

    async def reject(self, group: Group) -> None:
        await self.session.delete(group)
        await self.session.commit()

    async def mark_bot_left(self, group: Group) -> Group:
        group.is_approved = False
        await self.session.commit()
        return group

    async def ban(self, group: Group, reason: str) -> Group:
        group.is_banned = True
        group.ban_reason = reason
        group.is_frozen = False
        group.frozen_reason = None
        group.frozen_at = None
        await self.session.commit()
        return group

    async def unban(self, group: Group) -> Group:
        group.is_banned = False
        group.ban_reason = None
        await self.session.commit()
        return group

    async def freeze(self, group: Group, reason: str | None = None) -> Group:
        group.is_frozen = True
        group.frozen_reason = reason
        group.frozen_at = datetime.now(timezone.utc)
        await self.session.commit()
        return group

    async def unfreeze(self, group: Group) -> Group:
        group.is_frozen = False
        group.frozen_reason = None
        group.frozen_at = None
        await self.session.commit()
        return group

    async def soft_delete(self, group: Group) -> Group:
        group.is_deleted = True
        group.deleted_at = datetime.now(timezone.utc)
        group.is_approved = False
        group.is_frozen = False
        await self.session.commit()
        return group

    async def set_owner(self, group: Group, owner_user_id: int) -> Group:
        group.owner_user_id = owner_user_id
        await self.session.commit()
        return group

    async def update_metadata(self, group: Group, **fields) -> Group:
        allowed = {
            "group_name", "call_center_label", "tariff", "tariff_notes",
            "work_conditions", "participants_info", "contact_info", "notes",
        }
        for key, value in fields.items():
            if key in allowed:
                setattr(group, key, value)
        await self.session.commit()
        await self.session.refresh(group)
        return group

    async def get_all(self, *, include_deleted: bool = False) -> list[Group]:
        query = select(Group).order_by(Group.created_at.desc())
        if not include_deleted:
            query = query.where(Group.is_deleted.is_(False))
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_open_tickets_by_group(self, group_ids: list[int]) -> dict[int, int]:
        if not group_ids:
            return {}
        active = [TicketStatus.new, TicketStatus.in_progress, TicketStatus.waiting_info]
        result = await self.session.execute(
            select(Ticket.group_id, func.count())
            .where(Ticket.group_id.in_(group_ids), Ticket.status.in_(active))
            .group_by(Ticket.group_id)
        )
        return {int(row[0]): int(row[1]) for row in result.all() if row[0] is not None}
