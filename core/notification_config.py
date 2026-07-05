from __future__ import annotations

import copy
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.repositories.app_setting_repo import AppSettingRepository

logger = logging.getLogger(__name__)

NOTIFICATION_KEY = "notifications"

DEFAULT_EVENTS: dict[str, dict[str, bool]] = {
    "ticket_new": {"support_chats": True, "admin_chats": True},
    "ticket_status": {"user_dm": True, "source_group": True},
    "ticket_resolved": {"user_dm": True, "source_group": True},
    "group_pending": {"support_chats": True, "admin_chats": True},
    "deposit_new": {"support_chats": False, "admin_chats": True},
}


def _parse_chat_ids(raw: str, *fallback: int) -> list[int]:
    ids: list[int] = []
    if raw.strip():
        for part in raw.split(","):
            part = part.strip()
            if part:
                ids.append(int(part))
    if not ids:
        ids = [x for x in fallback if x]
    return ids


def env_defaults() -> dict[str, Any]:
    return {
        "support_chat_ids": _parse_chat_ids(
            settings.notify_support_chat_ids,
            settings.support_group_id,
        ),
        "admin_chat_ids": _parse_chat_ids(
            settings.notify_admin_chat_ids,
            settings.superadmin_telegram_id,
        ),
        "events": copy.deepcopy(DEFAULT_EVENTS),
    }


def _merge_events(base: dict[str, dict[str, bool]], stored: dict | None) -> dict[str, dict[str, bool]]:
    merged = copy.deepcopy(base)
    if not stored:
        return merged
    for event, flags in stored.items():
        if event not in merged or not isinstance(flags, dict):
            continue
        merged[event].update({k: bool(v) for k, v in flags.items()})
    return merged


def merge_config(stored: dict | None) -> dict[str, Any]:
    base = env_defaults()
    if not stored:
        return base

    support = stored.get("support_chat_ids")
    admin = stored.get("admin_chat_ids")
    if isinstance(support, list) and support:
        base["support_chat_ids"] = [int(x) for x in support]
    if isinstance(admin, list) and admin:
        base["admin_chat_ids"] = [int(x) for x in admin]
    base["events"] = _merge_events(base["events"], stored.get("events"))
    return base


def normalize_config(data: dict[str, Any]) -> dict[str, Any]:
    merged = merge_config(data)
    merged["support_chat_ids"] = list(dict.fromkeys(int(x) for x in merged["support_chat_ids"]))
    merged["admin_chat_ids"] = list(dict.fromkeys(int(x) for x in merged["admin_chat_ids"]))
    return merged


async def get_notification_config(session: AsyncSession | None = None) -> dict[str, Any]:
    if session is None:
        return env_defaults()
    repo = AppSettingRepository(session)
    stored = await repo.get_value(NOTIFICATION_KEY)
    return merge_config(stored)


async def save_notification_config(session: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    config = normalize_config(data)
    repo = AppSettingRepository(session)
    await repo.set_value(
        NOTIFICATION_KEY,
        config,
        description="Telegram notification routing and event toggles",
    )
    return config


async def replace_chat_id(session: AsyncSession, old_id: int, new_id: int) -> bool:
    config = await get_notification_config(session)
    changed = False
    for field in ("support_chat_ids", "admin_chat_ids"):
        ids: list[int] = config[field]
        if old_id not in ids:
            continue
        updated = [new_id if x == old_id else x for x in ids]
        if new_id not in updated:
            updated.append(new_id)
        config[field] = list(dict.fromkeys(updated))
        changed = True
    if changed:
        await save_notification_config(session, config)
        logger.info("Updated notification chat id %s → %s", old_id, new_id)
    return changed


def support_action_chat_ids(config: dict[str, Any]) -> set[int]:
    return set(config.get("support_chat_ids", [])) | set(config.get("admin_chat_ids", []))
