"""Бизнес-логика пополнений USDT."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.finance_config import get_finance_config
from db.models.finance import Deposit, DepositStatus
from db.models.user import User
from db.repositories.finance_repo import FinanceRepository, parse_usdt_amount
from services.audit import log_audit
from services.telegram_notify import notify_deposit_awaiting_review

logger = logging.getLogger(__name__)


class FinanceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


async def get_user_balance(session: AsyncSession, user_id: int) -> Decimal:
    repo = FinanceRepository(session)
    account = await repo.get_or_create_account(user_id)
    return Decimal(account.balance_usdt)


async def create_usdt_deposit(
    session: AsyncSession,
    user: User,
    amount_text: str,
) -> Deposit:
    cfg = await get_finance_config(session)
    try:
        amount = parse_usdt_amount(amount_text)
    except ValueError as exc:
        raise FinanceError(str(exc)) from exc
    min_d = Decimal(str(cfg["min_deposit_usdt"]))
    max_d = Decimal(str(cfg["max_deposit_usdt"]))
    if amount < min_d:
        raise FinanceError(f"Минимальная сумма: {min_d} USDT")
    if amount > max_d:
        raise FinanceError(f"Максимальная сумма: {max_d} USDT")

    repo = FinanceRepository(session)
    if await repo.count_active_deposits(user.id) >= 3:
        raise FinanceError("У вас уже есть активные заявки на пополнение. Дождитесь обработки.")

    wallet = await repo.pick_random_active_wallet()
    if not wallet:
        raise FinanceError("Пополнение временно недоступно. Обратитесь к администратору.", 503)

    deposit = await repo.create_deposit(
        user_id=user.id,
        wallet_id=wallet.id,
        amount=amount,
        ttl_hours=int(cfg["deposit_ttl_hours"]),
    )
    await log_audit(
        session,
        category="finance",
        action="deposit_created",
        actor=user,
        entity_type="deposit",
        entity_id=deposit.id,
        details={
            "amount_usdt": str(amount),
            "wallet_id": wallet.id,
            "wallet_address": wallet.address,
            "network": wallet.network,
        },
    )
    return deposit


async def mark_deposit_paid(
    session: AsyncSession,
    user: User,
    deposit_id: int,
    tx_hash: str | None = None,
) -> Deposit:
    repo = FinanceRepository(session)
    deposit = await repo.get_deposit(deposit_id)
    if not deposit or deposit.user_id != user.id:
        raise FinanceError("Заявка не найдена", 404)
    if deposit.status not in (DepositStatus.pending, DepositStatus.awaiting_review):
        raise FinanceError("Заявка уже обработана")
    if deposit.expires_at and deposit.expires_at < datetime.now(timezone.utc):
        await repo.update_deposit(deposit, status=DepositStatus.expired)
        raise FinanceError("Срок заявки истёк. Создайте новую.")

    fields = {"status": DepositStatus.awaiting_review}
    if tx_hash:
        fields["tx_hash"] = tx_hash.strip()[:128]
    deposit = await repo.update_deposit(deposit, **fields)
    await log_audit(
        session,
        category="finance",
        action="deposit_marked_paid",
        actor=user,
        entity_type="deposit",
        entity_id=deposit.id,
        details={"tx_hash": deposit.tx_hash},
    )
    deposit = await repo.get_deposit(deposit.id)
    if deposit:
        await notify_deposit_awaiting_review(session, deposit, user)
        try:
            from services.notion.finance_ledger import sync_deposit_to_ledger
            await sync_deposit_to_ledger(
                session, deposit, user, event="deposit_awaiting_review",
            )
        except Exception:
            logger.exception("Notion ledger sync (awaiting) failed for deposit %s", deposit.id)
    return deposit


async def confirm_deposit(
    session: AsyncSession,
    admin: User,
    deposit_id: int,
    *,
    admin_note: str | None = None,
) -> Deposit:
    repo = FinanceRepository(session)
    deposit = await repo.get_deposit(deposit_id)
    if not deposit:
        raise FinanceError("Заявка не найдена", 404)
    if deposit.status == DepositStatus.confirmed:
        return deposit
    if deposit.status not in (DepositStatus.pending, DepositStatus.awaiting_review):
        raise FinanceError(f"Нельзя подтвердить статус {deposit.status.value}")

    old_balance = await get_user_balance(session, deposit.user_id)
    await repo.add_balance(deposit.user_id, Decimal(deposit.amount_usdt))
    new_balance = await get_user_balance(session, deposit.user_id)

    deposit = await repo.update_deposit(
        deposit,
        status=DepositStatus.confirmed,
        confirmed_at=datetime.now(timezone.utc),
        confirmed_by=admin.id,
        admin_note=admin_note,
    )
    await log_audit(
        session,
        category="finance",
        action="deposit_confirmed",
        actor=admin,
        entity_type="deposit",
        entity_id=deposit.id,
        details={
            "amount_usdt": str(deposit.amount_usdt),
            "user_id": deposit.user_id,
            "balance_before": str(old_balance),
            "balance_after": str(new_balance),
        },
    )
    deposit = await repo.get_deposit(deposit.id)
    if deposit and deposit.user:
        try:
            from services.notion.finance_ledger import sync_deposit_to_ledger
            await sync_deposit_to_ledger(
                session, deposit, deposit.user, event="deposit_confirmed", actor=admin,
            )
        except Exception:
            logger.exception("Notion ledger sync (confirmed) failed for deposit %s", deposit.id)
    return deposit


async def reject_deposit(
    session: AsyncSession,
    admin: User,
    deposit_id: int,
    *,
    admin_note: str | None = None,
) -> Deposit:
    repo = FinanceRepository(session)
    deposit = await repo.get_deposit(deposit_id)
    if not deposit:
        raise FinanceError("Заявка не найдена", 404)
    if deposit.status in (DepositStatus.confirmed, DepositStatus.rejected):
        raise FinanceError("Заявка уже закрыта")

    deposit = await repo.update_deposit(
        deposit,
        status=DepositStatus.rejected,
        admin_note=admin_note,
    )
    await log_audit(
        session,
        category="finance",
        action="deposit_rejected",
        actor=admin,
        entity_type="deposit",
        entity_id=deposit.id,
        details={"admin_note": admin_note},
    )
    return deposit
