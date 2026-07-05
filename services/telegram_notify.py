"""Telegram-уведомления через Bot API (без aiogram)."""

from __future__ import annotations

import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.services.notification_config import get_notification_config
from db.models.finance import Deposit
from db.models.user import User

logger = logging.getLogger(__name__)


async def _send_html(chat_ids: list[int], text: str) -> bool:
    if not chat_ids:
        return False
    url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
    ok = False
    async with httpx.AsyncClient(timeout=15) as client:
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


def _collect_chat_ids(config: dict, event_key: str) -> list[int]:
    events = config.get("events", {}).get(event_key, {})
    chat_ids: list[int] = []
    if events.get("support_chats", True):
        chat_ids.extend(config.get("support_chat_ids", []))
    if events.get("admin_chats", True):
        chat_ids.extend(config.get("admin_chat_ids", []))
    return list(dict.fromkeys(chat_ids))


def _format_deposit_message(deposit: Deposit, user: User) -> str:
    wallet = deposit.wallet
    username = f"@{user.username}" if user.username else "нет username"
    name = " ".join(filter(None, [user.first_name, user.last_name])) or "—"
    tx = deposit.tx_hash or "не указан"
    wallet_line = "—"
    if wallet:
        wallet_line = f"<b>{wallet.network}</b>\n<code>{wallet.address}</code>"
    return (
        f"💰 <b>Заявка на пополнение #{deposit.id}</b>\n\n"
        f"👤 {name} {username}\n"
        f"🆔 ID: <code>{user.internal_id}</code>\n"
        f"💵 Сумма: <b>{deposit.amount_usdt}</b> USDT\n"
        f"🔗 TX: <code>{tx}</code>\n"
        f"📬 Кошелёк:\n{wallet_line}\n\n"
        f"Статус: ожидает проверки\n"
        f"Web CRM → Финансы → Заявки"
    )


async def notify_deposit_awaiting_review(
    session: AsyncSession,
    deposit: Deposit,
    user: User,
) -> bool:
    """Уведомить админов/поддержку о заявке после «Я оплатил»."""
    config = await get_notification_config(session)
    chat_ids = _collect_chat_ids(config, "deposit_new")
    if not chat_ids:
        return False
    text = _format_deposit_message(deposit, user)
    return await _send_html(chat_ids, text)
