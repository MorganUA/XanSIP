"""Создание заявок пользователя (личный чат / Mini App)."""

from __future__ import annotations

import asyncio
import logging

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.support_notify import notify_support_new_ticket_http
from bot.catalog.group_errors import get_group_preset
from bot.config import settings
from bot.utils.ticket_validation import (
    increment_daily_counter,
    set_cooldown,
    validate_sip_for_new_ticket,
)
from db.models.ticket import ErrorType, TicketSource
from db.models.user import User
from db.repositories.sip_repo import SipRepository
from db.repositories.ticket_repo import TicketRepository

logger = logging.getLogger(__name__)


async def _notify_support_background(
    session: AsyncSession,
    ticket_id: int,
    user_id: int,
    sip_id: int,
    *,
    error_label: str,
) -> None:
    """Fire-and-forget: не блокирует ответ Mini App."""
    from db.base import async_session_maker
    from db.repositories.sip_repo import SipRepository as SipRepo
    from db.repositories.ticket_repo import TicketRepository as TicketRepo
    from db.repositories.user_repo import UserRepository

    try:
        async with async_session_maker() as bg_session:
            ticket = await TicketRepo(bg_session).get_by_id(ticket_id)
            user = await UserRepository(bg_session).get_by_id(user_id)
            sip = await SipRepo(bg_session).get_by_id(sip_id)
            if ticket and user:
                await notify_support_new_ticket_http(
                    bg_session, ticket, user, sip, error_label=error_label,
                )
    except Exception:
        logger.exception("Background support notify failed for ticket %s", ticket_id)


async def create_personal_ticket(
    session: AsyncSession,
    redis: Redis,
    *,
    user: User,
    sip_id: int,
    preset_id: str,
) -> dict:
    preset = get_group_preset(preset_id)
    if not preset:
        raise ValueError("Неизвестный тип ошибки")

    sip_repo = SipRepository(session)
    sip = await sip_repo.get_by_id(sip_id)
    if not sip or sip.user_id != user.id:
        raise PermissionError("SIP не найден")

    error = await validate_sip_for_new_ticket(
        redis=redis, user=user, sip=sip, session=session,
    )
    if error:
        raise ValueError(error.replace("⛔ ", "").replace("⚠️ ", ""))

    ticket_repo = TicketRepository(session)
    ticket = await ticket_repo.create(
        user_id=user.id,
        sip_id=sip.id,
        error_type=preset.error_type,
        description=preset.label,
        source=TicketSource.personal_chat,
    )

    await set_cooldown(redis, user.id, sip.id, settings.cooldown_minutes)
    await increment_daily_counter(redis, user.id)

    asyncio.create_task(
        _notify_support_background(
            session,
            ticket.id,
            user.id,
            sip.id,
            error_label=preset.label,
        )
    )

    return {
        "ticket_id": ticket.id,
        "sip_number": sip.sip_number,
        "error_label": preset.label,
        "notified": True,
    }
