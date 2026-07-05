"""Настройки интеграции Notion (app_settings key: notion)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from db.repositories.app_setting_repo import AppSettingRepository

NOTION_KEY = "notion"

DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "default_database_id": "",
    "databases": {
        "tickets": "",
        "deposits": "",
        "users": "",
        "finance_ledger": "",
    },
    "sync_events": {
        "ticket_new": False,
        "ticket_status": False,
        "deposit_awaiting_review": False,
        "deposit_confirmed": False,
    },
}


def env_defaults() -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    cfg["enabled"] = settings.notion_enabled
    if settings.notion_database_id:
        cfg["default_database_id"] = settings.notion_database_id
    return cfg


def _deep_merge(base: dict[str, Any], stored: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in stored.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


async def get_notion_config(session: AsyncSession) -> dict[str, Any]:
    repo = AppSettingRepository(session)
    stored = await repo.get_value(NOTION_KEY)
    cfg = env_defaults()
    if stored:
        cfg = _deep_merge(cfg, stored)
    if settings.notion_enabled:
        cfg["enabled"] = True
    if settings.notion_database_id and not cfg.get("default_database_id"):
        cfg["default_database_id"] = settings.notion_database_id
    return cfg


async def save_notion_config(session: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    repo = AppSettingRepository(session)
    cfg = await get_notion_config(session)
    cfg = _deep_merge(cfg, data)
    await repo.set_value(NOTION_KEY, cfg, description="Notion integration settings")
    return cfg


def is_notion_active(config: dict[str, Any] | None = None) -> bool:
    cfg = config or env_defaults()
    return bool(settings.notion_enabled or cfg.get("enabled")) and bool(settings.notion_api_token.strip())
