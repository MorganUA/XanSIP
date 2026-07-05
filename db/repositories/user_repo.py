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

    async def get_by_ids(self, user_ids: list[int]) -> dict[int, User]:
        if not user_ids:
            return {}
        result = await self.session.execute(
            select(User).where(User.id.in_(user_ids))
        )
        return {u.id: u for u in result.scalars().all()}

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

    async def sync_profile(
        self,
        user: User,
        *,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> User:
        changed = False
        if user.username != username:
            user.username = username
            changed = True
        if user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if user.last_name != last_name:
            user.last_name = last_name
            changed = True
        if changed:
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

    async def list_recent(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None,
    ) -> list[User]:
        from sqlalchemy import or_

        query = select(User).order_by(User.created_at.desc())
        if search:
            term = search.strip()
            if term.isdigit():
                query = query.where(
                    or_(
                        User.telegram_id == int(term),
                        User.internal_id.ilike(f"%{term}%"),
                    )
                )
            else:
                like = f"%{term}%"
                query = query.where(
                    or_(
                        User.internal_id.ilike(like),
                        User.username.ilike(like),
                        User.first_name.ilike(like),
                    )
                )
        query = query.limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())

