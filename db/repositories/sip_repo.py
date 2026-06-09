from sqlalchemy import select
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

    async def create(
        self,
        user_id: int,
        sip_number: str,
        description: str | None = None,
        provider: str | None = None,
        added_by: int | None = None,
    ) -> SipAccount:
        sip = SipAccount(
            user_id=user_id,
            sip_number=sip_number,
            description=description,
            provider=provider,
            added_by=added_by,
        )
        self.session.add(sip)
        await self.session.commit()
        await self.session.refresh(sip)
        return sip

    async def update_status(self, sip: SipAccount, status: SipStatus) -> SipAccount:
        sip.status = status
        await self.session.commit()
        return sip
