from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models.finance import Deposit, DepositStatus, UserAccount, UsdtWallet


class FinanceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_account(self, user_id: int) -> UserAccount:
        result = await self.session.execute(
            select(UserAccount).where(UserAccount.user_id == user_id)
        )
        account = result.scalar_one_or_none()
        if account:
            return account
        account = UserAccount(user_id=user_id, balance_usdt=Decimal("0"))
        self.session.add(account)
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def set_balance(self, user_id: int, balance: Decimal) -> UserAccount:
        account = await self.get_or_create_account(user_id)
        account.balance_usdt = balance
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def add_balance(self, user_id: int, amount: Decimal) -> UserAccount:
        account = await self.get_or_create_account(user_id)
        account.balance_usdt = Decimal(account.balance_usdt) + amount
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def list_wallets(self, *, active_only: bool = False) -> list[UsdtWallet]:
        q = select(UsdtWallet).order_by(UsdtWallet.id)
        if active_only:
            q = q.where(UsdtWallet.is_active.is_(True))
        return list((await self.session.execute(q)).scalars().all())

    async def get_wallet(self, wallet_id: int) -> UsdtWallet | None:
        return await self.session.get(UsdtWallet, wallet_id)

    async def create_wallet(self, **fields) -> UsdtWallet:
        wallet = UsdtWallet(**fields)
        self.session.add(wallet)
        await self.session.commit()
        await self.session.refresh(wallet)
        return wallet

    async def update_wallet(self, wallet: UsdtWallet, **fields) -> UsdtWallet:
        for k, v in fields.items():
            if hasattr(wallet, k):
                setattr(wallet, k, v)
        await self.session.commit()
        await self.session.refresh(wallet)
        return wallet

    async def delete_wallet(self, wallet: UsdtWallet) -> None:
        await self.session.delete(wallet)
        await self.session.commit()

    async def pick_random_active_wallet(self) -> UsdtWallet | None:
        wallets = await self.list_wallets(active_only=True)
        if not wallets:
            return None
        return random.choice(wallets)

    async def create_deposit(
        self,
        *,
        user_id: int,
        wallet_id: int,
        amount: Decimal,
        ttl_hours: int,
    ) -> Deposit:
        expires = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        deposit = Deposit(
            user_id=user_id,
            wallet_id=wallet_id,
            amount_usdt=amount,
            status=DepositStatus.pending,
            expires_at=expires,
        )
        self.session.add(deposit)
        await self.session.commit()
        await self.session.refresh(deposit, attribute_names=["wallet"])
        return deposit

    async def get_deposit(self, deposit_id: int) -> Deposit | None:
        result = await self.session.execute(
            select(Deposit)
            .options(selectinload(Deposit.wallet), selectinload(Deposit.user))
            .where(Deposit.id == deposit_id)
        )
        return result.scalar_one_or_none()

    async def list_deposits(
        self,
        *,
        user_id: int | None = None,
        status: DepositStatus | None = None,
        limit: int = 100,
    ) -> list[Deposit]:
        q = (
            select(Deposit)
            .options(selectinload(Deposit.wallet), selectinload(Deposit.user))
            .order_by(Deposit.created_at.desc())
            .limit(limit)
        )
        if user_id is not None:
            q = q.where(Deposit.user_id == user_id)
        if status is not None:
            q = q.where(Deposit.status == status)
        return list((await self.session.execute(q)).scalars().all())

    async def update_deposit(self, deposit: Deposit, **fields) -> Deposit:
        for k, v in fields.items():
            if hasattr(deposit, k):
                setattr(deposit, k, v)
        await self.session.commit()
        await self.session.refresh(deposit)
        return deposit

    async def count_active_deposits(self, user_id: int) -> int:
        active = [DepositStatus.pending, DepositStatus.awaiting_review]
        result = await self.session.execute(
            select(Deposit.id).where(
                Deposit.user_id == user_id,
                Deposit.status.in_(active),
            )
        )
        return len(result.all())


def parse_usdt_amount(text: str) -> Decimal:
    raw = text.strip().replace(",", ".").replace(" ", "")
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError("Некорректная сумма") from exc
    if value <= 0:
        raise ValueError("Сумма должна быть больше 0")
    return value.quantize(Decimal("0.000001"))
