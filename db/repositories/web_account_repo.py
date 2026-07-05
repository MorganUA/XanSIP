from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.web_account import WebAccount


class WebAccountRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, account_id: int) -> WebAccount | None:
        result = await self.session.execute(
            select(WebAccount).where(WebAccount.id == account_id)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> WebAccount | None:
        result = await self.session.execute(
            select(WebAccount).where(WebAccount.username == username)
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> list[WebAccount]:
        result = await self.session.execute(
            select(WebAccount)
            .where(WebAccount.is_active.is_(True))
            .order_by(WebAccount.is_primary.desc(), WebAccount.username)
        )
        return list(result.scalars().all())

    async def create(self, account: WebAccount) -> WebAccount:
        self.session.add(account)
        await self.session.commit()
        await self.session.refresh(account)
        return account
