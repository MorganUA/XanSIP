import logging

import httpx

from bot.config import settings

logger = logging.getLogger(__name__)

EVENT_TICKET_RESOLVED = "ticket.resolved"
EVENT_TICKET_CREATED = "ticket.created"
EVENT_TICKET_STATUS_CHANGED = "ticket.status_changed"


async def dispatch_bot_webhook(event: str, payload: dict) -> bool:
    url = f"{settings.bot_webhook_url.rstrip('/')}/internal/webhook"
    headers = {
        "Content-Type": "application/json",
        "X-Bot-Secret": settings.bot_api_secret,
    }
    body = {"event": event, "payload": payload}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=body, headers=headers)
            response.raise_for_status()
            return True
    except Exception:
        logger.exception("Bot webhook dispatch failed: event=%s", event)
        return False


async def notify_ticket_resolved(
    *,
    ticket_id: int,
    group_chat_id: int | None,
    sip_number: str | None = None,
    error_label: str | None = None,
) -> bool:
    return await notify_ticket_status_changed(
        ticket_id=ticket_id,
        new_status="resolved",
        comment=None,
    )


async def notify_ticket_status_changed(
    *,
    ticket_id: int,
    new_status: str,
    old_status: str | None = None,
    comment: str | None = None,
) -> bool:
    return await dispatch_bot_webhook(
        EVENT_TICKET_STATUS_CHANGED,
        {
            "ticket_id": ticket_id,
            "old_status": old_status,
            "new_status": new_status,
            "comment": comment,
        },
    )
