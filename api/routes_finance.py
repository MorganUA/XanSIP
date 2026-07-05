"""Finance, audit, system registry API."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session, get_web_actor
from api.rbac import require_admin
from api.services.audit import log_audit
from api.services.finance_service import (
    FinanceError,
    confirm_deposit,
    get_user_balance,
    reject_deposit,
)
from bot.services.finance_config import get_finance_config, save_finance_config
from bot.utils.admin_audit import log_admin_action
from db.models.finance import DepositStatus
from db.models.user import User, UserRole
from db.repositories.app_setting_repo import AppSettingRepository
from db.repositories.audit_repo import AuditRepository
from db.repositories.finance_repo import FinanceRepository
from db.repositories.user_repo import UserRepository

router = APIRouter(tags=["finance"])


def _require_admin(actor: User) -> None:
    require_admin(actor)


def _serialize_wallet(w) -> dict:
    return {
        "id": w.id,
        "address": w.address,
        "label": w.label,
        "network": w.network,
        "is_active": w.is_active,
        "notes": w.notes,
        "created_at": w.created_at.isoformat() if w.created_at else None,
    }


def _serialize_deposit(d) -> dict:
    return {
        "id": d.id,
        "user_id": d.user_id,
        "user_internal_id": d.user.internal_id if d.user else None,
        "amount_usdt": str(d.amount_usdt),
        "status": d.status.value,
        "tx_hash": d.tx_hash,
        "admin_note": d.admin_note,
        "wallet": _serialize_wallet(d.wallet) if d.wallet else None,
        "expires_at": d.expires_at.isoformat() if d.expires_at else None,
        "confirmed_at": d.confirmed_at.isoformat() if d.confirmed_at else None,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


class WalletBody(BaseModel):
    address: str = Field(min_length=10, max_length=128)
    label: str | None = Field(default=None, max_length=120)
    network: str = Field(default="TRC20", max_length=32)
    is_active: bool = True
    notes: str | None = None


class WalletPatchBody(BaseModel):
    address: str | None = Field(default=None, max_length=128)
    label: str | None = Field(default=None, max_length=120)
    network: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None
    notes: str | None = None


class FinanceConfigBody(BaseModel):
    min_deposit_usdt: float | None = None
    max_deposit_usdt: float | None = None
    deposit_ttl_hours: int | None = None
    instruction_text: str | None = None
    currency_label: str | None = None


class DepositNoteBody(BaseModel):
    admin_note: str | None = None
    tx_hash: str | None = Field(default=None, max_length=128)
    amount_usdt: str | None = None
    status: str | None = None


class BalancePatchBody(BaseModel):
    balance_usdt: str


class SettingBody(BaseModel):
    value: dict
    description: str | None = None


class CellPatchBody(BaseModel):
    table: str
    row_id: str
    field: str
    value: str | int | float | bool | None


@router.get("/api/finance/config")
async def finance_config_get(session: AsyncSession = Depends(get_session)):
    return await get_finance_config(session)


@router.put("/api/finance/config")
async def finance_config_put(
    body: FinanceConfigBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_web_actor),
):
    _require_admin(actor)
    payload = body.model_dump(exclude_unset=True)
    old = await get_finance_config(session)
    cfg = await save_finance_config(session, payload)
    await log_admin_action(
        session, actor, "finance_config_update",
        entity_type="finance_config", entity_id=0,
        old_value=old, new_value=cfg,
    )
    return cfg


@router.get("/api/finance/wallets")
async def list_wallets(session: AsyncSession = Depends(get_session)):
    repo = FinanceRepository(session)
    return {"items": [_serialize_wallet(w) for w in await repo.list_wallets()]}


@router.post("/api/finance/wallets")
async def create_wallet(
    body: WalletBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_web_actor),
):
    _require_admin(actor)
    repo = FinanceRepository(session)
    wallet = await repo.create_wallet(**body.model_dump())
    await log_admin_action(
        session, actor, "wallet_create",
        entity_type="usdt_wallet", entity_id=wallet.id,
        new_value=_serialize_wallet(wallet),
    )
    return _serialize_wallet(wallet)


@router.patch("/api/finance/wallets/{wallet_id}")
async def patch_wallet(
    wallet_id: int,
    body: WalletPatchBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_web_actor),
):
    _require_admin(actor)
    repo = FinanceRepository(session)
    wallet = await repo.get_wallet(wallet_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    old = _serialize_wallet(wallet)
    wallet = await repo.update_wallet(wallet, **body.model_dump(exclude_unset=True))
    await log_admin_action(
        session, actor, "wallet_update",
        entity_type="usdt_wallet", entity_id=wallet.id,
        old_value=old, new_value=_serialize_wallet(wallet),
    )
    return _serialize_wallet(wallet)


@router.delete("/api/finance/wallets/{wallet_id}")
async def delete_wallet(
    wallet_id: int,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_web_actor),
):
    _require_admin(actor)
    repo = FinanceRepository(session)
    wallet = await repo.get_wallet(wallet_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    old = _serialize_wallet(wallet)
    await repo.delete_wallet(wallet)
    await log_admin_action(
        session, actor, "wallet_delete",
        entity_type="usdt_wallet", entity_id=wallet_id,
        old_value=old,
    )
    return {"ok": True}


@router.get("/api/finance/deposits")
async def list_deposits(
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    repo = FinanceRepository(session)
    st = DepositStatus(status) if status else None
    items = await repo.list_deposits(status=st, limit=200)
    return {"items": [_serialize_deposit(d) for d in items]}


@router.post("/api/finance/deposits/{deposit_id}/confirm")
async def api_confirm_deposit(
    deposit_id: int,
    body: DepositNoteBody | None = None,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_web_actor),
):
    _require_admin(actor)
    try:
        deposit = await confirm_deposit(
            session, actor, deposit_id,
            admin_note=body.admin_note if body else None,
        )
    except FinanceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return _serialize_deposit(deposit)


@router.post("/api/finance/deposits/{deposit_id}/reject")
async def api_reject_deposit(
    deposit_id: int,
    body: DepositNoteBody | None = None,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_web_actor),
):
    _require_admin(actor)
    try:
        deposit = await reject_deposit(
            session, actor, deposit_id,
            admin_note=body.admin_note if body else None,
        )
    except FinanceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return _serialize_deposit(deposit)


@router.patch("/api/finance/deposits/{deposit_id}")
async def patch_deposit(
    deposit_id: int,
    body: DepositNoteBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_web_actor),
):
    _require_admin(actor)
    repo = FinanceRepository(session)
    deposit = await repo.get_deposit(deposit_id)
    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")
    old = _serialize_deposit(deposit)
    fields = body.model_dump(exclude_unset=True)
    if "status" in fields and fields["status"]:
        fields["status"] = DepositStatus(fields["status"])
    if "amount_usdt" in fields and fields["amount_usdt"]:
        fields["amount_usdt"] = Decimal(fields["amount_usdt"])
    deposit = await repo.update_deposit(deposit, **fields)
    await log_admin_action(
        session, actor, "deposit_patch",
        entity_type="deposit", entity_id=deposit.id,
        old_value=old, new_value=_serialize_deposit(deposit),
    )
    return _serialize_deposit(deposit)


@router.get("/api/finance/balances")
async def list_balances(session: AsyncSession = Depends(get_session)):
    user_repo = UserRepository(session)
    finance_repo = FinanceRepository(session)
    users = await user_repo.list_recent(limit=500)
    items = []
    for u in users:
        acc = await finance_repo.get_or_create_account(u.id)
        items.append({
            "user_id": u.id,
            "internal_id": u.internal_id,
            "telegram_id": u.telegram_id,
            "balance_usdt": str(acc.balance_usdt),
        })
    return {"items": items}


@router.patch("/api/finance/balances/{user_id}")
async def patch_balance(
    user_id: int,
    body: BalancePatchBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_web_actor),
):
    _require_admin(actor)
    repo = FinanceRepository(session)
    old_acc = await repo.get_or_create_account(user_id)
    old = str(old_acc.balance_usdt)
    new_bal = Decimal(body.balance_usdt)
    acc = await repo.set_balance(user_id, new_bal)
    await log_admin_action(
        session, actor, "balance_set",
        entity_type="user_account", entity_id=user_id,
        old_value={"balance_usdt": old},
        new_value={"balance_usdt": str(acc.balance_usdt)},
    )
    return {"user_id": user_id, "balance_usdt": str(acc.balance_usdt)}


@router.get("/api/audit")
async def list_audit(
    category: str | None = None,
    limit: int = Query(default=200, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    repo = AuditRepository(session)
    events = await repo.list_events(category=category, limit=limit, offset=offset)
    return {
        "items": [
            {
                "id": e.id,
                "actor_user_id": e.actor_user_id,
                "actor_label": e.actor_label,
                "category": e.category,
                "action": e.action,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "details": e.details,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
        "readonly": True,
    }


@router.get("/api/system/settings")
async def list_settings(session: AsyncSession = Depends(get_session)):
    repo = AppSettingRepository(session)
    rows = await repo.list_all()
    return {
        "items": [
            {
                "key": r.key,
                "value": r.value,
                "description": r.description,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ],
    }


@router.put("/api/system/settings/{key}")
async def put_setting(
    key: str,
    body: SettingBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_web_actor),
):
    _require_admin(actor)
    repo = AppSettingRepository(session)
    old = await repo.get_value(key)
    await repo.set_value(key, body.value, description=body.description)
    await log_admin_action(
        session, actor, "setting_update",
        entity_type="app_setting", entity_id=0,
        old_value={"key": key, "value": old},
        new_value={"key": key, "value": body.value},
    )
    return {"ok": True, "key": key}


@router.patch("/api/system/cell")
async def patch_cell(
    body: CellPatchBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_web_actor),
):
    """Универсальное редактирование ячеек (whitelist таблиц/полей)."""
    _require_admin(actor)
    table, field, row_id = body.table, body.field, body.row_id

    if table == "app_settings":
        repo = AppSettingRepository(session)
        old = await repo.get_value(row_id)
        if not isinstance(body.value, dict):
            raise HTTPException(status_code=400, detail="value must be object for app_settings")
        await repo.set_value(row_id, body.value)
        await log_admin_action(
            session, actor, "cell_patch",
            entity_type=table, entity_id=0,
            old_value={"key": row_id, "value": old},
            new_value={"key": row_id, "value": body.value},
        )
        return {"ok": True}

    if table == "usdt_wallets":
        repo = FinanceRepository(session)
        wallet = await repo.get_wallet(int(row_id))
        if not wallet:
            raise HTTPException(status_code=404)
        old = _serialize_wallet(wallet)
        await repo.update_wallet(wallet, **{field: body.value})
        await log_admin_action(
            session, actor, "cell_patch",
            entity_type=table, entity_id=int(row_id),
            old_value=old, new_value={field: body.value},
        )
        return {"ok": True}

    if table == "user_accounts" and field == "balance_usdt":
        repo = FinanceRepository(session)
        acc = await repo.set_balance(int(row_id), Decimal(str(body.value)))
        await log_admin_action(
            session, actor, "cell_patch",
            entity_type=table, entity_id=int(row_id),
            new_value={"balance_usdt": str(acc.balance_usdt)},
        )
        return {"ok": True}

    raise HTTPException(status_code=400, detail=f"Unsupported table/field: {table}.{field}")
