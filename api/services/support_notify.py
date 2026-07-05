"""Уведомление поддержки без aiogram (для API / Mini App)."""

from __future__ import annotations

import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.error_labels import ERROR_TYPE_LABELS
from bot.config import settings
from bot.services.notification_config import get_notification_config
from db.models.sip_account import SipAccount
from db.models.ticket import Ticket
from db.models.user import User

logger = logging.getLogger(__name__)


def _format_ticket_message(
    ticket: Ticket,
    user: User,
    sip: SipAccount | None,
    *,
    error_label: str | None = None,
) -> str:
    sip_str = sip.sip_number if sip else "не указан"
    label = error_label or ERROR_TYPE_LABELS.get(ticket.error_type, ticket.error_type.value)
    name = user.first_name or ""
    username = f"@{user.username}" if user.username else "нет username"
    return (
        f"🚨 <b>Новая заявка #{ticket.id}</b> (Mini App)\n\n"
        f"👤 {name} {username}\n"
        f"🆔 ID: <code>{user.internal_id}</code>\n"
        f"📞 SIP: <code>{sip_str}</code>\n"
        f"⚠️ {label}\n"
        f"📝 {ticket.description}\n"
        f"📍 Личный чат / Mini App"
    )


async def notify_support_new_ticket_http(
    session: AsyncSession,
    ticket: Ticket,
    user: User,
    sip: SipAccount | None,
    *,
    error_label: str | None = None,
) -> bool:
    config = await get_notification_config(session)
    events = config["events"].get("ticket_new", {})
    text = _format_ticket_message(ticket, user, sip, error_label=error_label)
    chat_ids: list[int] = []
    if events.get("support_chats", True):
        chat_ids.extend(config.get("support_chat_ids", []))
    if events.get("admin_chats", True):
        chat_ids.extend(config.get("admin_chat_ids", []))
    chat_ids = list(dict.fromkeys(chat_ids))
    if not chat_ids:
        return False

    url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
    ok = False
    async with httpx.AsyncClient(timeout=8) as client:
        for chat_id in chat_ids:
            try:
                res = await client.post(url, json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                })
                res.raise_for_status()
                ok = True
            except Exception:
                logger.exception("Failed to notify chat %s", chat_id)
    return ok
