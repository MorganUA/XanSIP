"""Notion integration API (admin)."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session, get_web_actor
from api.rbac import require_admin
from bot.config import settings
from bot.services.notion_config import get_notion_config, is_notion_active, save_notion_config
from bot.utils.admin_audit import log_admin_action
from db.models.user import User, UserRole
from db.repositories.finance_repo import FinanceRepository
from services.notion.errors import NotionError
from services.notion.finance_ledger import (
    LEDGER_DB_TITLE,
    create_finance_ledger_database,
    expected_property_names,
    link_finance_ledger,
    resolve_ledger_database_id,
    sync_deposit_to_ledger,
    validate_ledger_database,
)
from services.notion.service import notion_error_to_status, resolve_notion_client, test_connection

router = APIRouter(tags=["notion"])


def _require_admin(actor: User) -> None:
    require_admin(actor)


class NotionConfigBody(BaseModel):
    enabled: bool | None = None
    default_database_id: str | None = None
    databases: dict[str, str] | None = None
    sync_events: dict[str, bool] | None = None


class NotionSearchBody(BaseModel):
    query: str = ""
    page_size: int = Field(default=10, ge=1, le=50)


class NotionQueryBody(BaseModel):
    filter_obj: dict[str, Any] | None = None
    sorts: list[dict[str, Any]] | None = None
    page_size: int = Field(default=10, ge=1, le=50)
    start_cursor: str | None = None


class NotionCreatePageBody(BaseModel):
    database_id: str | None = None
    properties: dict[str, Any]
    children: list[dict[str, Any]] | None = None


@router.get("/api/notion/guide")
async def notion_guide(session: AsyncSession = Depends(get_session)):
    config = await get_notion_config(session)
    return {
        "has_token": bool(settings.notion_api_token.strip()),
        "active": is_notion_active(config),
        "api_version": settings.notion_api_version,
        "env": {
            "NOTION_API_TOKEN": {
                "label": "API-токен интеграции",
                "required": True,
                "set": bool(settings.notion_api_token.strip()),
                "hint": "Создайте Internal Integration на notion.so/my-integrations и добавьте secret_… в .env на сервере. Через веб-панель токен не задаётся — только на сервере.",
            },
            "NOTION_ENABLED": {
                "label": "Включить интеграцию",
                "required": False,
                "set": settings.notion_enabled,
                "hint": "NOTION_ENABLED=true в .env или переключатель «Активна» в CRM.",
            },
            "NOTION_DATABASE_ID": {
                "label": "База по умолчанию",
                "required": False,
                "set": bool(settings.notion_database_id or config.get("default_database_id")),
                "hint": "UUID базы Notion (32 символа с дефисами). Можно задать в .env или в мастере ниже.",
            },
            "NOTION_API_VERSION": {
                "label": "Версия API",
                "required": False,
                "set": True,
                "value": settings.notion_api_version,
                "hint": "Заголовок Notion-Version. По умолчанию 2022-06-28.",
            },
        },
        "algorithm": [
            {
                "step": 1,
                "title": "Создание интеграции в Notion",
                "body": "Notion → Settings → Connections → Develop or manage integrations → New integration. Скопируйте Internal Integration Secret (secret_…).",
            },
            {
                "step": 2,
                "title": "Доступ к базам данных",
                "body": "Откройте каждую нужную базу в Notion → ⋯ → Connections → подключите вашу интеграцию. Без этого API вернёт object_not_found.",
            },
            {
                "step": 3,
                "title": "Токен на сервере",
                "body": "Добавьте NOTION_API_TOKEN и NOTION_ENABLED=true в .env, перезапустите docker compose. Токен не хранится в браузере.",
            },
            {
                "step": 4,
                "title": "Привязка баз в CRM",
                "body": "В мастере укажите Database ID для заявок, депозитов и пользователей. ID берётся из URL базы: notion.so/…/{database_id}?v=…",
            },
            {
                "step": 5,
                "title": "События синхронизации",
                "body": "Включите нужные sync_events. При срабатывании события CRM вызывает Notion API: create_page в соответствующей базе. Все вызовы логируются в audit_events.",
            },
            {
                "step": 6,
                "title": "Проверка",
                "body": "Мастер → «Проверить подключение» → «Проверить базу». Успешный ответ users/me и схема properties базы подтверждают готовность.",
            },
        ],
        "flow": [
            "Событие в SIP CRM (новая заявка, депозит, …)",
            "→ services/notion проверяет enabled + sync_events",
            "→ NotionClient.create_database_page()",
            "→ запись в audit_events (категория notion)",
        ],
        "database_slots": {
            "tickets": "Заявки колл-центра",
            "deposits": "Пополнения USDT",
            "users": "Пользователи / клиенты",
            "finance_ledger": "Учет доходов и расходов XanaXGSM",
        },
        "sync_event_labels": {
            "ticket_new": "Новая заявка",
            "ticket_status": "Изменение статуса заявки",
            "deposit_awaiting_review": "Депозит на проверке",
            "deposit_confirmed": "Депозит подтверждён",
        },
        "config": config,
        "finance_ledger": {
            "title": LEDGER_DB_TITLE,
            "database_id": resolve_ledger_database_id(config),
            "expected_columns": expected_property_names(),
        },
    }


@router.get("/api/notion/status")
async def notion_status(session: AsyncSession = Depends(get_session)):
    config = await get_notion_config(session)
    return {
        "active": is_notion_active(config),
        "has_token": bool(settings.notion_api_token.strip()),
        "config": config,
    }


@router.get("/api/notion/config")
async def notion_config_get(session: AsyncSession = Depends(get_session)):
    return await get_notion_config(session)


@router.put("/api/notion/config")
async def notion_config_put(
    body: NotionConfigBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_web_actor),
):
    _require_admin(actor)
    old = await get_notion_config(session)
    payload = body.model_dump(exclude_unset=True)
    cfg = await save_notion_config(session, payload)
    await log_admin_action(
        session, actor, "notion_config_update",
        entity_type="notion_config", entity_id=0,
        old_value=old, new_value=cfg,
    )
    return cfg


@router.post("/api/notion/test")
async def notion_test(
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_web_actor),
):
    _require_admin(actor)
    try:
        return await test_connection(session)
    except NotionError as exc:
        raise HTTPException(status_code=notion_error_to_status(exc), detail=str(exc)) from exc


@router.post("/api/notion/search")
async def notion_search(
    body: NotionSearchBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_web_actor),
):
    _require_admin(actor)
    try:
        client, _ = await resolve_notion_client(session)
        return await client.search(query=body.query, page_size=body.page_size)
    except NotionError as exc:
        raise HTTPException(status_code=notion_error_to_status(exc), detail=str(exc)) from exc


@router.get("/api/notion/databases/{database_id}")
async def notion_get_database(
    database_id: str,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_web_actor),
):
    _require_admin(actor)
    try:
        client, _ = await resolve_notion_client(session)
        return await client.get_database(database_id)
    except NotionError as exc:
        raise HTTPException(status_code=notion_error_to_status(exc), detail=str(exc)) from exc


@router.post("/api/notion/databases/{database_id}/query")
async def notion_query_database(
    database_id: str,
    body: NotionQueryBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_web_actor),
):
    _require_admin(actor)
    try:
        client, _ = await resolve_notion_client(session)
        return await client.query_database(
            database_id,
            filter_obj=body.filter_obj,
            sorts=body.sorts,
            page_size=body.page_size,
            start_cursor=body.start_cursor,
        )
    except NotionError as exc:
        raise HTTPException(status_code=notion_error_to_status(exc), detail=str(exc)) from exc


@router.post("/api/notion/pages")
async def notion_create_page(
    body: NotionCreatePageBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_web_actor),
):
    _require_admin(actor)
    try:
        client, config = await resolve_notion_client(session)
        database_id = body.database_id or config.get("default_database_id")
        if not database_id:
            raise HTTPException(status_code=400, detail="database_id is required")
        page = await client.create_database_page(
            database_id,
            body.properties,
            children=body.children,
        )
        await log_admin_action(
            session, actor, "notion_page_create",
            entity_type="notion_page", entity_id=0,
            new_value={"page_id": page.get("id"), "database_id": database_id},
        )
        return page
    except NotionError as exc:
        raise HTTPException(status_code=notion_error_to_status(exc), detail=str(exc)) from exc


class FinanceLedgerCreateBody(BaseModel):
    parent_page_id: str = Field(min_length=32, max_length=64)


class FinanceLedgerLinkBody(BaseModel):
    database_id: str = Field(min_length=32, max_length=64)


@router.get("/api/notion/finance-ledger/schema")
async def finance_ledger_schema():
    return {
        "title": LEDGER_DB_TITLE,
        "columns": expected_property_names(),
    }


@router.post("/api/notion/finance-ledger/create")
async def finance_ledger_create(
    body: FinanceLedgerCreateBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_web_actor),
):
    _require_admin(actor)
    try:
        db = await create_finance_ledger_database(
            session, body.parent_page_id, actor=actor,
        )
        validation = None
        if db.get("id"):
            client, _ = await resolve_notion_client(session)
            validation = await validate_ledger_database(client, db["id"])
        return {"ok": True, "database_id": db.get("id"), "url": db.get("url"), "validation": validation}
    except NotionError as exc:
        raise HTTPException(status_code=notion_error_to_status(exc), detail=str(exc)) from exc


@router.post("/api/notion/finance-ledger/link")
async def finance_ledger_link(
    body: FinanceLedgerLinkBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_web_actor),
):
    _require_admin(actor)
    try:
        return await link_finance_ledger(session, body.database_id, actor=actor)
    except NotionError as exc:
        raise HTTPException(status_code=notion_error_to_status(exc), detail=str(exc)) from exc


@router.get("/api/notion/finance-ledger/validate")
async def finance_ledger_validate(
    database_id: str,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_web_actor),
):
    _require_admin(actor)
    try:
        client, _ = await resolve_notion_client(session)
        return await validate_ledger_database(client, database_id)
    except NotionError as exc:
        raise HTTPException(status_code=notion_error_to_status(exc), detail=str(exc)) from exc


@router.post("/api/notion/finance-ledger/sync/{deposit_id}")
async def finance_ledger_sync_deposit(
    deposit_id: int,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_web_actor),
):
    _require_admin(actor)
    repo = FinanceRepository(session)
    deposit = await repo.get_deposit(deposit_id)
    if not deposit or not deposit.user:
        raise HTTPException(status_code=404, detail="Deposit not found")
    try:
        page = await sync_deposit_to_ledger(
            session, deposit, deposit.user,
            event="deposit_confirmed", actor=actor,
        )
        if not page:
            raise HTTPException(status_code=400, detail="Sync disabled or not configured")
        return {"ok": True, "page_id": page.get("id"), "url": page.get("url")}
    except NotionError as exc:
        raise HTTPException(status_code=notion_error_to_status(exc), detail=str(exc)) from exc
