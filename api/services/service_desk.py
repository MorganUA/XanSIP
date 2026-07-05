from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.group_errors import get_group_preset
from bot.utils.ticket_validation import (
    increment_daily_counter,
    set_cooldown,
    validate_sip_for_new_ticket,
)
from bot.config import settings
from db.repositories.group_repo import GroupRepository
from db.repositories.sip_repo import SipRepository
from db.repositories.ticket_repo import TicketRepository
from db.repositories.user_repo import UserRepository


class ServiceDeskError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


async def create_group_service_desk_ticket(
    session: AsyncSession,
    redis: Redis,
    *,
    sip_number: str,
    error_preset_id: str,
    initiator_telegram_id: int,
    group_chat_id: int,
) -> dict:
    preset = get_group_preset(error_preset_id)
    if not preset:
        raise ServiceDeskError("Unknown error preset", 400)

    group_repo = GroupRepository(session)
    group = await group_repo.get_by_telegram_id(group_chat_id)
    if not group or not group.is_approved:
        raise ServiceDeskError("Group not authorized", 403)
    if group.is_banned:
        raise ServiceDeskError("Group is banned", 403)
    if group.is_frozen:
        reason = group.frozen_reason or "не указана"
        raise ServiceDeskError(f"Group is frozen: {reason}", 403)

    user_repo = UserRepository(session)
    sip_repo = SipRepository(session)
    ticket_repo = TicketRepository(session)

    sip_owner_id = group.owner_user_id
    if not sip_owner_id:
        initiator = await user_repo.get_by_telegram_id(initiator_telegram_id)
        if not initiator:
            raise ServiceDeskError("Group owner not set. Contact admin.", 400)
        sip_owner_id = initiator.id

    sip_owner = await user_repo.get_by_id(sip_owner_id)
    if not sip_owner:
        raise ServiceDeskError("SIP owner not found", 404)

    sip = await sip_repo.get_by_number_and_user(sip_number.strip(), sip_owner.id)
    if not sip:
        raise ServiceDeskError(
            f"SIP {sip_number} not found for group owner {sip_owner.internal_id}",
            404,
        )

    validation_error = await validate_sip_for_new_ticket(
        redis=redis, user=sip_owner, sip=sip, session=session,
    )
    if validation_error:
        raise ServiceDeskError(validation_error, 429)

    ticket = await ticket_repo.create_service_desk(
        user_id=sip_owner.id,
        sip_id=sip.id,
        group_id=group.id,
        error_type=preset.error_type,
        description=preset.label,
        initiator_telegram_id=initiator_telegram_id,
        error_preset_id=error_preset_id,
        sip_number_snapshot=sip_number.strip(),
    )

    await set_cooldown(redis, sip_owner.id, sip.id, settings.cooldown_minutes)
    await increment_daily_counter(redis, sip_owner.id)

    return {
        "ticket_id": ticket.id,
        "sip_number": sip_number.strip(),
        "error_label": preset.label,
        "group_chat_id": group.telegram_group_id,
    }
