"""База «Учет доходов и расходов XanaXGSM» — схема, создание и синхронизация."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.notion_config import get_notion_config, is_notion_active, save_notion_config
from db.models.finance import Deposit, DepositStatus
from db.models.user import User
from services.audit import log_audit
from services.notion.client import NotionClient, get_notion_client
from services.notion.errors import NotionDisabledError, NotionError
from services.notion import properties as P

logger = logging.getLogger(__name__)

LEDGER_DB_TITLE = "Учет доходов и расходов XanaXGSM"
LEDGER_DESCRIPTION = (
    "Финансовая база для ежедневного учета доходов, расходов, франшизы, "
    "чистого дохода и возвратов участникам."
)

# Имена колонок (как в Notion)
COL_OPERATION = "Операция"
COL_DATE = "Дата"
COL_CASH_FLOW = "Движение кассы"
COL_SHARE_THREE = "Доля на троих"
COL_SOURCE = "Источник оплаты"
COL_CATEGORY = "Категория"
COL_COMMENT = "Комментарий"
COL_RETURN_TO = "Кому вернуть"
COL_WHO = "Кто внес / потратил"
COL_STATUS = "Статус"
COL_AMOUNT_USD = "Сумма USD"
COL_TYPE = "Тип"
COL_FRANCHISE = "Франшиза 40%"
COL_NET_INCOME = "Чистый доход после франшизы"

# Значения select
SRC_PERSONAL = "Личные средства"
SRC_USDT = "USDT"
SRC_BANK = "Банк"
SRC_CASH = "Касса"

CAT_TOPUP = "Пополнение кассы"
CAT_INCOME = "Доход"
CAT_EXPENSE = "Расход"
CAT_RETURN = "Возврат"

WHO_TEAM = "Команда"

ST_PENDING = "Ожидает"
ST_ACCOUNTED = "Учтено"
ST_REJECTED = "Отклонено"

TYPE_BUDGET = "Вклад в бюджет"
TYPE_INCOME = "Доход"
TYPE_EXPENSE = "Расход"
TYPE_RETURN = "Возврат"

SIPCRM_TAG = "SIPCRM:#"


def _select_options(names: list[str], colors: list[str] | None = None) -> list[dict]:
    colors = colors or ["default"] * len(names)
    return [{"name": n, "color": c} for n, c in zip(names, colors)]


def ledger_database_schema() -> dict[str, Any]:
    """Схема properties для POST /databases."""
    return {
        COL_OPERATION: {"title": {}},
        COL_DATE: {"date": {}},
        COL_AMOUNT_USD: {"number": {"format": "dollar"}},
        COL_CASH_FLOW: {
            "formula": {
                "expression": (
                    'if(or(prop("Тип") == "Расход", prop("Тип") == "Возврат"), '
                    "-prop(\"Сумма USD\"), prop(\"Сумма USD\"))"
                ),
            },
        },
        COL_SHARE_THREE: {
            "formula": {
                "expression": 'if(prop("Тип") == "Доход", prop("Движение кассы") / 3, 0)',
            },
        },
        COL_SOURCE: {
            "select": {
                "options": _select_options(
                    [SRC_PERSONAL, SRC_USDT, SRC_BANK, SRC_CASH],
                    ["orange", "purple", "blue", "green"],
                ),
            },
        },
        COL_CATEGORY: {
            "select": {
                "options": _select_options(
                    [CAT_TOPUP, CAT_INCOME, CAT_EXPENSE, CAT_RETURN],
                    ["blue", "green", "red", "yellow"],
                ),
            },
        },
        COL_COMMENT: {"rich_text": {}},
        COL_RETURN_TO: {"select": {"options": []}},
        COL_WHO: {
            "select": {
                "options": _select_options([WHO_TEAM], ["blue"]),
            },
        },
        COL_STATUS: {
            "select": {
                "options": _select_options(
                    [ST_PENDING, ST_ACCOUNTED, ST_REJECTED],
                    ["yellow", "green", "red"],
                ),
            },
        },
        COL_TYPE: {
            "select": {
                "options": _select_options(
                    [TYPE_BUDGET, TYPE_INCOME, TYPE_EXPENSE, TYPE_RETURN],
                    ["blue", "green", "red", "yellow"],
                ),
            },
        },
        COL_FRANCHISE: {
            "formula": {
                "expression": 'if(prop("Тип") == "Доход", prop("Сумма USD") * 0.4, 0)',
            },
        },
        COL_NET_INCOME: {
            "formula": {
                "expression": (
                    'if(prop("Тип") == "Доход", '
                    'prop("Сумма USD") - prop("Франшиза 40%"), 0)'
                ),
            },
        },
    }


def expected_property_names() -> list[str]:
    return list(ledger_database_schema().keys())


REQUIRED_LEDGER_COLUMNS = [
    COL_OPERATION,
    COL_DATE,
    COL_AMOUNT_USD,
    COL_SOURCE,
    COL_CATEGORY,
    COL_COMMENT,
    COL_WHO,
    COL_STATUS,
    COL_TYPE,
]


def deposit_comment_tag(deposit_id: int) -> str:
    return f"{SIPCRM_TAG}{deposit_id}"


def build_deposit_ledger_properties(
    deposit: Deposit,
    user: User,
    *,
    accounted: bool = False,
    rejected: bool = False,
) -> dict[str, Any]:
    amount = float(Decimal(deposit.amount_usdt))
    when = deposit.confirmed_at or deposit.created_at or datetime.now(timezone.utc)
    date_str = when.strftime("%Y-%m-%d")

    if rejected:
        status = ST_REJECTED
    elif accounted:
        status = ST_ACCOUNTED
    else:
        status = ST_PENDING

    wallet = deposit.wallet.address if deposit.wallet else "—"
    network = deposit.wallet.network if deposit.wallet else "—"
    comment = (
        f"{deposit_comment_tag(deposit.id)} | "
        f"user:{user.internal_id} | tg:{user.telegram_id} | "
        f"tx:{deposit.tx_hash or '—'} | {network}:{wallet}"
    )

    return {
        COL_OPERATION: P.title(f"Пополнение USDT #{deposit.id}"),
        COL_DATE: P.date(date_str),
        COL_AMOUNT_USD: P.number(amount),
        COL_SOURCE: P.select(SRC_USDT),
        COL_CATEGORY: P.select(CAT_TOPUP),
        COL_COMMENT: P.rich_text(comment[:2000]),
        COL_WHO: P.select(WHO_TEAM),
        COL_STATUS: P.select(status),
        COL_TYPE: P.select(TYPE_BUDGET),
    }


def resolve_ledger_database_id(config: dict[str, Any]) -> str | None:
    dbs = config.get("databases") or {}
    for key in ("finance_ledger", "deposits", "default"):
        val = dbs.get(key) or (config.get("default_database_id") if key == "default" else "")
        if val:
            return str(val).strip()
    return (config.get("default_database_id") or "").strip() or None


async def create_finance_ledger_database(
    session: AsyncSession,
    parent_page_id: str,
    *,
    actor: User | None = None,
) -> dict[str, Any]:
    client = get_notion_client()
    if not client.is_configured():
        raise NotionDisabledError("NOTION_API_TOKEN не задан")

    parent_page_id = parent_page_id.strip().replace("-", "")
    if len(parent_page_id) == 32:
        parent_page_id = f"{parent_page_id[:8]}-{parent_page_id[8:12]}-{parent_page_id[12:16]}-{parent_page_id[16:20]}-{parent_page_id[20:]}"

    db = await client.create_database(
        parent_page_id=parent_page_id,
        title=LEDGER_DB_TITLE,
        properties=ledger_database_schema(),
        icon_emoji="🏛️",
    )
    db_id = db.get("id", "")
    if db_id:
        try:
            await client.append_blocks(db_id, [P.paragraph_block(LEDGER_DESCRIPTION)])
        except NotionError:
            logger.warning("Could not append ledger description blocks")

        cfg = await save_notion_config(session, {
            "enabled": True,
            "default_database_id": db_id,
            "databases": {
                "finance_ledger": db_id,
                "deposits": db_id,
            },
            "sync_events": {
                "deposit_awaiting_review": True,
                "deposit_confirmed": True,
            },
        })
        await log_audit(
            session,
            category="notion",
            action="finance_ledger_created",
            actor=actor,
            entity_type="notion_database",
            entity_id=db_id,
            details={"title": LEDGER_DB_TITLE, "config": cfg},
        )
    return db


async def validate_ledger_database(client: NotionClient, database_id: str) -> dict[str, Any]:
    schema = await client.get_database(database_id)
    props = set((schema.get("properties") or {}).keys())
    expected = set(expected_property_names())
    required = set(REQUIRED_LEDGER_COLUMNS)
    missing_required = sorted(required - props)
    missing_optional = sorted((expected - required) - props)
    extra = sorted(props - expected)
    return {
        "ok": not missing_required,
        "database_id": database_id,
        "title": _plain_title(schema.get("title")),
        "missing_columns": missing_required,
        "missing_optional_columns": missing_optional,
        "extra_columns": extra,
        "matched_columns": sorted(expected & props),
    }


def _plain_title(title_arr: list | None) -> str:
    if not title_arr:
        return ""
    return title_arr[0].get("plain_text", "") if isinstance(title_arr[0], dict) else ""


async def link_finance_ledger(
    session: AsyncSession,
    database_id: str,
    *,
    actor: User | None = None,
) -> dict[str, Any]:
    client = get_notion_client()
    validation = await validate_ledger_database(client, database_id.strip())
    if not validation["ok"] and validation["missing_columns"]:
        raise NotionError(
            f"База не совпадает со схемой XanaXGSM. Нет колонок: {', '.join(validation['missing_columns'])}",
            status_code=400,
        )
    cfg = await save_notion_config(session, {
        "enabled": True,
        "default_database_id": database_id.strip(),
        "databases": {
            "finance_ledger": database_id.strip(),
            "deposits": database_id.strip(),
        },
        "sync_events": {
            "deposit_awaiting_review": True,
            "deposit_confirmed": True,
        },
    })
    await log_audit(
        session,
        category="notion",
        action="finance_ledger_linked",
        actor=actor,
        entity_type="notion_database",
        entity_id=database_id,
        details={"validation": validation, "config": cfg},
    )
    return {"validation": validation, "config": cfg}


async def _find_deposit_page(client: NotionClient, database_id: str, deposit_id: int) -> dict | None:
    result = await client.query_database(
        database_id,
        filter_obj={
            "property": COL_COMMENT,
            "rich_text": {"contains": deposit_comment_tag(deposit_id)},
        },
        page_size=1,
    )
    items = result.get("results") or []
    return items[0] if items else None


async def sync_deposit_to_ledger(
    session: AsyncSession,
    deposit: Deposit,
    user: User,
    *,
    event: str,
    actor: User | None = None,
) -> dict[str, Any] | None:
    """Записать или обновить операцию в Notion. Возвращает page или None если sync выключен."""
    config = await get_notion_config(session)
    if not is_notion_active(config):
        return None
    events = config.get("sync_events") or {}
    if not events.get(event):
        return None

    database_id = resolve_ledger_database_id(config)
    if not database_id:
        logger.warning("Notion finance ledger: database_id not configured")
        return None

    client = get_notion_client()
    accounted = event == "deposit_confirmed" or deposit.status == DepositStatus.confirmed
    rejected = deposit.status == DepositStatus.rejected
    pending = event == "deposit_awaiting_review" and not accounted and not rejected

    if not (accounted or rejected or pending):
        return None

    props = build_deposit_ledger_properties(
        deposit, user, accounted=accounted, rejected=rejected,
    )

    try:
        existing = await _find_deposit_page(client, database_id, deposit.id)
        if existing:
            page = await client.update_page(existing["id"], properties=props)
            action = "deposit_ledger_updated"
        else:
            page = await client.create_database_page(database_id, props)
            action = "deposit_ledger_created"

        await log_audit(
            session,
            category="notion",
            action=action,
            actor=actor or user,
            entity_type="notion_page",
            entity_id=page.get("id"),
            details={
                "deposit_id": deposit.id,
                "event": event,
                "database_id": database_id,
                "amount_usdt": str(deposit.amount_usdt),
            },
        )
        return page
    except NotionError:
        logger.exception("Notion ledger sync failed for deposit %s", deposit.id)
        raise
