from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.user import User, UserRole


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        telegram_id: int,
        internal_id: str,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        role: UserRole = UserRole.user,
    ) -> User:
        user = User(
            telegram_id=telegram_id,
            internal_id=internal_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            role=role,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update_username(self, user: User, username: str | None) -> User:
        user.username = username
        await self.session.commit()
        return user

    async def ban(self, user: User, reason: str, banned_by_id: int) -> User:
        from datetime import datetime, timezone
        user.is_banned = True
        user.ban_reason = reason
        user.banned_at = datetime.now(timezone.utc)
        user.banned_by = banned_by_id
        await self.session.commit()
        return user

    async def unban(self, user: User) -> User:
        user.is_banned = False
        user.ban_reason = None
        user.banned_at = None
        user.banned_by = None
        await self.session.commit()
        return user

    async def count_all(self) -> int:
        from sqlalchemy import func
        result = await self.session.execute(
            select(func.count()).select_from(User)
        )
        return result.scalar_one()

