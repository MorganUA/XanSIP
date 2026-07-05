import logging
from typing import Any

from aiohttp import web
from aiogram import Bot

from bot.config import settings
from bot.services.notification_config import get_notification_config
from bot.utils.formatting import escape_html
from bot.utils.notify import notify_user_ticket_update
from bot.utils.telegram_send import send_message_safe
from bot.utils.ticket_status_messages import (
    build_ticket_status_message,
    ticket_status_notify_event,
)
from db.base import async_session_maker
from db.models.ticket import TicketStatus
from db.repositories.group_repo import GroupRepository
from db.repositories.ticket_repo import TicketRepository
from db.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)

EVENT_TICKET_RESOLVED = "ticket.resolved"
EVENT_TICKET_CREATED = "ticket.created"
EVENT_TICKET_STATUS_CHANGED = "ticket.status_changed"


def _check_secret(request: web.Request) -> bool:
    import secrets

    secret = request.headers.get("X-Bot-Secret", "")
    expected = settings.bot_api_secret
    if not secret or not expected:
        return False
    return secrets.compare_digest(secret, expected)


async def health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "bot-webhook"})


async def handle_webhook(request: web.Request) -> web.Response:
    if not _check_secret(request):
        return web.json_response({"detail": "Forbidden"}, status=403)

    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return web.json_response({"detail": "Invalid JSON"}, status=400)

    event = body.get("event")
    payload = body.get("payload") or {}

    bot: Bot = request.app["bot"]

    if event == EVENT_TICKET_RESOLVED:
        await _on_ticket_resolved(bot, payload)
    elif event == EVENT_TICKET_STATUS_CHANGED:
        await _on_ticket_status_changed(bot, payload)
    elif event == EVENT_TICKET_CREATED:
        await _on_ticket_created(bot, payload)
    else:
        logger.info("Webhook event ignored: %s", event)
        return web.json_response({"ok": True, "handled": False})

    return web.json_response({"ok": True, "handled": True, "event": event})


async def _on_ticket_resolved(bot: Bot, payload: dict[str, Any]) -> None:
    ticket_id = payload.get("ticket_id")
    group_chat_id = payload.get("group_chat_id")
    sip_number = payload.get("sip_number")
    error_label = payload.get("error_label")

    if not ticket_id or not group_chat_id:
        logger.warning("ticket.resolved missing fields: %s", payload)
        return

    async with async_session_maker() as session:
        config = await get_notification_config(session)
        events = config["events"].get("ticket_resolved", {})
        if not events.get("source_group", True):
            return

        parts = [f"✅ Заявка №{ticket_id} решена, можете продолжать работу."]
        if sip_number:
            parts.append(f"SIP: <code>{escape_html(str(sip_number))}</code>")
        if error_label:
            parts.append(f"Ошибка: {escape_html(str(error_label))}")
        text = "\n".join(parts)

        try:
            await send_message_safe(
                bot, int(group_chat_id), text, session=session,
            )
        except Exception:
            logger.exception(
                "Failed to notify group %s about resolved ticket #%s",
                group_chat_id,
                ticket_id,
            )


async def _on_ticket_status_changed(bot: Bot, payload: dict[str, Any]) -> None:
    ticket_id = payload.get("ticket_id")
    new_status_str = payload.get("new_status")
    comment = payload.get("comment")

    if not ticket_id or not new_status_str:
        logger.warning("ticket.status_changed missing fields: %s", payload)
        return

    try:
        new_status = TicketStatus(new_status_str)
    except ValueError:
        logger.warning("ticket.status_changed invalid status: %s", new_status_str)
        return

    async with async_session_maker() as session:
        ticket_repo = TicketRepository(session)
        user_repo = UserRepository(session)
        group_repo = GroupRepository(session)

        ticket = await ticket_repo.get_by_id(int(ticket_id))
        if not ticket:
            logger.warning("ticket.status_changed: ticket #%s not found", ticket_id)
            return

        user = await user_repo.get_by_id(ticket.user_id)
        if not user:
            logger.warning("ticket.status_changed: user for ticket #%s not found", ticket_id)
            return

        group = None
        if ticket.group_id:
            group = await group_repo.get_by_id(ticket.group_id)

        status_text = build_ticket_status_message(
            ticket.id, new_status, comment=comment,
        )
        event_key = ticket_status_notify_event(new_status)
        delivered = await notify_user_ticket_update(
            bot,
            user,
            ticket,
            status_text,
            group=group,
            session=session,
            event=event_key,
        )
        if not delivered:
            logger.warning(
                "ticket.status_changed: no delivery for ticket #%s → %s",
                ticket_id,
                new_status_str,
            )


async def _on_ticket_created(bot: Bot, payload: dict[str, Any]) -> None:
    logger.debug("ticket.created webhook payload: %s", payload)


async def _on_ticket_resolved_from_db(bot: Bot, ticket_id: int) -> None:
    """Fallback: load group from DB if payload incomplete."""
    async with async_session_maker() as session:
        ticket_repo = TicketRepository(session)
        group_repo = GroupRepository(session)
        ticket = await ticket_repo.get_by_id(ticket_id)
        if not ticket or not ticket.group_id:
            return
        group = await group_repo.get_by_id(ticket.group_id)
        if not group:
            return
        await _on_ticket_resolved(
            bot,
            {
                "ticket_id": ticket.id,
                "group_chat_id": group.telegram_group_id,
                "sip_number": ticket.sip_number_snapshot,
            },
        )


def create_webhook_app(bot: Bot) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app.router.add_get("/internal/health", health)
    app.router.add_post("/internal/webhook", handle_webhook)
    return app
