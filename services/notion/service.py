"""Высокоуровневые операции Notion с учётом конфигурации SIP CRM."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.notion_config import env_defaults, get_notion_config, is_notion_active
from services.notion.client import NotionClient, get_notion_client
from services.notion.errors import NotionDisabledError, NotionError


async def resolve_notion_client(session: AsyncSession | None = None) -> tuple[NotionClient, dict[str, Any]]:
    config = await get_notion_config(session) if session else env_defaults()
    if not is_notion_active(config):
        raise NotionDisabledError()
    client = get_notion_client()
    return client, config


async def test_connection(session: AsyncSession | None = None) -> dict[str, Any]:
    client, config = await resolve_notion_client(session)
    me = await client.get_me()
    return {
        "ok": True,
        "bot_type": me.get("type"),
        "workspace_name": me.get("name"),
        "enabled": config.get("enabled", False),
    }


def notion_error_to_status(exc: NotionError) -> int:
    if exc.status_code:
        return exc.status_code
    return 502
