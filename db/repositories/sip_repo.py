from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.sip_account import SipAccount, SipStatus


class SipRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_user_id(self, user_id: int) -> list[SipAccount]:
        result = await self.session.execute(
            select(SipAccount)
            .where(SipAccount.user_id == user_id)
            .order_by(SipAccount.sip_number)
        )
        return list(result.scalars().all())

    async def get_active_by_user_id(self, user_id: int) -> list[SipAccount]:
        result = await self.session.execute(
            select(SipAccount)
            .where(
                SipAccount.user_id == user_id,
                SipAccount.status == SipStatus.active,
            )
            .order_by(SipAccount.sip_number)
        )
        return list(result.scalars().all())

    async def get_by_id(self, sip_id: int) -> SipAccount | None:
        result = await self.session.execute(
            select(SipAccount).where(SipAccount.id == sip_id)
        )
        return result.scalar_one_or_none()

    async def get_by_number_and_user(
        self, sip_number: str, user_id: int
    ) -> SipAccount | None:
        result = await self.session.execute(
            select(SipAccount).where(
                SipAccount.sip_number == sip_number,
                SipAccount.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_number(self, sip_number: str) -> SipAccount | None:
        result = await self.session.execute(
            select(SipAccount).where(SipAccount.sip_number == sip_number)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: int,
        sip_number: str,
        description: str | None = None,
        provider: str | None = None,
        added_by: int | None = None,
        auth_username: str | None = None,
        auth_secret_enc: str | None = None,
    ) -> SipAccount:
        sip = SipAccount(
            user_id=user_id,
            sip_number=sip_number,
            description=description,
            provider=provider,
            added_by=added_by,
            auth_username=auth_username,
            auth_secret_enc=auth_secret_enc,
        )
        self.session.add(sip)
        await self.session.commit()
        await self.session.refresh(sip)
        return sip

    async def set_credentials(
        self,
        sip: SipAccount,
        *,
        auth_username: str | None,
        auth_secret_enc: str | None,
    ) -> SipAccount:
        sip.auth_username = auth_username.strip() if auth_username else None
        sip.auth_secret_enc = auth_secret_enc
        await self.session.commit()
        await self.session.refresh(sip)
        return sip

    async def update_status(self, sip: SipAccount, status: SipStatus) -> SipAccount:
        sip.status = status
        await self.session.commit()
        return sip

    async def list_recent(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: SipStatus | None = None,
        search: str | None = None,
    ) -> list[SipAccount]:
        from sqlalchemy.orm import selectinload
        from db.models.user import User

        query = (
            select(SipAccount)
            .options(selectinload(SipAccount.user))
            .order_by(SipAccount.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status:
            query = query.where(SipAccount.status == status)
        if search:
            term = f"%{search.strip()}%"
            query = query.join(User, SipAccount.user_id == User.id).where(
                or_(
                    SipAccount.sip_number.ilike(term),
                    User.internal_id.ilike(term),
                    User.username.ilike(term),
                )
            )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_by_status(self) -> dict[str, int]:
        result = await self.session.execute(
            select(SipAccount.status, func.count()).group_by(SipAccount.status)
        )
        return {row[0].value: row[1] for row in result.all()}

    async def count_all(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(SipAccount)
        )
        return int(result.scalar_one())
