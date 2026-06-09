from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from db.models.user import User
from db.models.ticket import ErrorType, TicketSource
from db.repositories.sip_repo import SipRepository
from db.repositories.ticket_repo import TicketRepository
from db.repositories.group_repo import GroupRepository
from db.repositories.user_repo import UserRepository
from bot.utils.notify import notify_support_new_ticket
from bot.handlers.tickets import (
    check_cooldown, set_cooldown,
    check_daily_limit, increment_daily_counter,
)
from bot.config import settings

router = Router()


@router.message(Command("err"), F.chat.type.in_({"group", "supergroup"}))
async def group_err_command(
    message: Message,
    user: User,
    session: AsyncSession,
    bot: Bot,
    redis: Redis,
):
    """Команда /err в группе."""
    group_repo = GroupRepository(session)
    group = await group_repo.get_by_telegram_id(message.chat.id)

    # Проверяем что группа одобрена
    if not group or not group.is_approved:
        await message.reply("⛔ Эта группа не авторизована для отправки заявок.")
        return

    if group.is_banned:
        await message.reply("🚫 Эта группа заблокирована.")
        return

    # Определяем владельца группы для поиска SIP
    if group.owner_user_id:
        user_repo = UserRepository(session)
        owner = await user_repo.get_by_id(group.owner_user_id)
        sip_owner = owner if owner else user
    else:
        sip_owner = user

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.reply(
            "⚠️ Формат: <code>/err номер_сип описание</code>\n"
            "Пример: <code>/err 100 нет регистрации</code>",
            parse_mode="HTML",
        )
        return

    sip_number = args[1]
    description = args[2]

    sip_repo = SipRepository(session)
    ticket_repo = TicketRepository(session)

    sip = await sip_repo.get_by_number_and_user(sip_number, sip_owner.id)
    if not sip:
        await message.reply(
            f"⛔ SIP <code>{sip_number}</code> не найден.",
            parse_mode="HTML",
        )
        return

    open_ticket = await ticket_repo.get_open_by_sip(sip.id)
    if open_ticket:
        await message.reply(
            f"⚠️ По SIP {sip_number} уже есть открытая заявка #{open_ticket.id}."
        )
        return

    if await check_cooldown(redis, sip_owner.id, sip.id):
        await message.reply(
            f"⏳ Подождите {settings.cooldown_minutes} минут перед следующей заявкой."
        )
        return

    if await check_daily_limit(redis, sip_owner.id, settings.max_tickets_per_day):
        await message.reply(
            f"⚠️ Достигнут дневной лимит заявок ({settings.max_tickets_per_day})."
        )
        return

    ticket = await ticket_repo.create(
        user_id=sip_owner.id,
        sip_id=sip.id,
        group_id=group.id,
        error_type=ErrorType.other,
        description=description,
        source=TicketSource.group_chat,
    )

    await set_cooldown(redis, sip_owner.id, sip.id, settings.cooldown_minutes)
    await increment_daily_counter(redis, sip_owner.id)

    msg_id = await notify_support_new_ticket(bot, ticket, sip_owner, sip, group)
    if msg_id:
        await ticket_repo.set_support_message_id(ticket, msg_id)

    await message.reply(
        f"✅ Заявка <b>#{ticket.id}</b> создана по SIP <code>{sip_number}</code>.\n"
        "Поддержка уведомлена.",
        parse_mode="HTML",
    )
