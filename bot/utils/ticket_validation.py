from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from db.models.sip_account import SipAccount, SipStatus
from db.models.user import User
from db.repositories.ticket_repo import TicketRepository

SIP_STATUS_LABELS = {
    SipStatus.active: "активен",
    SipStatus.frozen: "заморожен",
    SipStatus.disabled: "отключён",
}


async def check_cooldown(redis: Redis, user_id: int, sip_id: int) -> bool:
    key = f"cooldown:sip:{sip_id}:user:{user_id}"
    return await redis.get(key) is not None


async def set_cooldown(redis: Redis, user_id: int, sip_id: int, minutes: int) -> None:
    key = f"cooldown:sip:{sip_id}:user:{user_id}"
    await redis.set(key, 1, ex=minutes * 60)


async def check_daily_limit(redis: Redis, user_id: int, max_tickets: int) -> bool:
    key = f"daily_tickets:user:{user_id}"
    count = await redis.get(key)
    if count is None:
        return False
    return int(count) >= max_tickets


async def increment_daily_counter(redis: Redis, user_id: int) -> None:
    key = f"daily_tickets:user:{user_id}"
    pipe = redis.pipeline()
    await pipe.incr(key)
    await pipe.expire(key, 86400)
    await pipe.execute()


async def can_report_sip(
    *,
    redis: Redis,
    user: User,
    sip: SipAccount,
    session: AsyncSession,
) -> bool:
    if sip.status != SipStatus.active:
        return False
    ticket_repo = TicketRepository(session)
    if await ticket_repo.get_open_by_sip(sip.id):
        return False
    if await check_cooldown(redis, user.id, sip.id):
        return False
    if await check_daily_limit(redis, user.id, settings.max_tickets_per_day):
        return False
    return True


async def validate_sip_for_new_ticket(
    *,
    redis: Redis,
    user: User,
    sip: SipAccount,
    session: AsyncSession,
) -> str | None:
    if sip.status != SipStatus.active:
        status = SIP_STATUS_LABELS.get(sip.status, sip.status.value)
        return f"⛔ SIP {sip.sip_number} недоступен (статус: {status})."

    ticket_repo = TicketRepository(session)
    open_ticket = await ticket_repo.get_open_by_sip(sip.id)
    if open_ticket:
        return (
            f"⚠️ По SIP {sip.sip_number} уже есть открытая заявка #{open_ticket.id}.\n"
            "Дождитесь её решения."
        )

    if await check_cooldown(redis, user.id, sip.id):
        return (
            f"⏳ Подождите {settings.cooldown_minutes} минут "
            "перед следующей заявкой по этому SIP."
        )

    if await check_daily_limit(redis, user.id, settings.max_tickets_per_day):
        return (
            f"⚠️ Вы достигли лимита заявок за сегодня "
            f"({settings.max_tickets_per_day})."
        )

    return None
