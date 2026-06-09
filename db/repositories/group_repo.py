from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.group import Group


class GroupRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_telegram_id(self, telegram_group_id: int) -> Group | None:
        result = await self.session.execute(
            select(Group).where(Group.telegram_group_id == telegram_group_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, group_id: int) -> Group | None:
        result = await self.session.execute(
            select(Group).where(Group.id == group_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        telegram_group_id: int,
        group_name: str | None = None,
        owner_user_id: int | None = None,
    ) -> Group:
        group = Group(
            telegram_group_id=telegram_group_id,
            group_name=group_name,
            owner_user_id=owner_user_id,
            is_approved=False,
        )
        self.session.add(group)
        await self.session.commit()
        await self.session.refresh(group)
        return group

    async def approve(self, group: Group, approved_by_id: int) -> Group:
        from datetime import datetime, timezone
        group.is_approved = True
        group.approved_by = approved_by_id
        group.approved_at = datetime.now(timezone.utc)
        await self.session.commit()
        return group

    async def reject(self, group: Group) -> None:
        await self.session.delete(group)
        await self.session.commit()

    async def ban(self, group: Group, reason: str) -> Group:
        group.is_banned = True
        group.ban_reason = reason
        await self.session.commit()
        return group

    async def unban(self, group: Group) -> Group:
        group.is_banned = False
        group.ban_reason = None
        await self.session.commit()
        return group

    async def set_owner(self, group: Group, owner_user_id: int) -> Group:
        group.owner_user_id = owner_user_id
        await self.session.commit()
        return group

    async def get_all(self) -> list[Group]:
        result = await self.session.execute(
            select(Group).order_by(Group.created_at.desc())
        )
        return list(result.scalars().all())
