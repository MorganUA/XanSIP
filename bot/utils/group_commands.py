"""Общие хелперы для групповых команд /status, /sips."""

from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.utils.group_access import group_access_error
from bot.keyboards.sip_menu import STATUS_ICONS, STATUS_LABELS
from bot.utils.formatting import escape_html
from bot.utils.ticket_display import format_ticket_short
from db.models.group import Group
from db.models.user import User
from db.repositories.sip_repo import SipRepository
from db.repositories.ticket_repo import TicketRepository


async def resolve_group_context(
    message: Message,
    session: AsyncSession,
    group_repo,
) -> tuple[Group | None, str | None]:
    group = await group_repo.get_by_telegram_id(message.chat.id)
    err = group_access_error(group)
    return group, err


async def send_group_status(message: Message, group: Group, session: AsyncSession) -> None:
    repo = TicketRepository(session)
    tickets = await repo.list_active_by_group(group.id)
    if not tickets:
        await message.reply(
            "📋 <b>Активные заявки группы</b>\n\n"
            "Открытых заявок нет.\n"
            "Создать: <code>/err номер_сип</code>",
            parse_mode="HTML",
        )
        return
    lines = [f"📋 <b>Активные заявки</b> ({len(tickets)})\n"]
    for t in tickets:
        lines.append(f"• {format_ticket_short(t)}")
    lines.append("\nСоздать новую: <code>/err номер_сип</code>")
    await message.reply("\n".join(lines), parse_mode="HTML")


async def send_group_sips(
    message: Message,
    group: Group,
    session: AsyncSession,
    user_repo,
) -> None:
    if not group.owner_user_id:
        await message.reply(
            "📞 <b>SIP-номера</b>\n\n"
            "Владелец группы не назначен.\n"
            "Администратор: <code>/set_group_owner id telegram_id</code>",
            parse_mode="HTML",
        )
        return

    owner = await user_repo.get_by_id(group.owner_user_id)
    if not owner:
        await message.reply("⚠️ Владелец группы не найден в системе.")
        return

    sip_repo = SipRepository(session)
    sips = await sip_repo.get_active_by_user_id(owner.id)
    if not sips:
        await message.reply(
            f"📞 У владельца <code>{escape_html(owner.internal_id)}</code> "
            "нет активных SIP-номеров.",
            parse_mode="HTML",
        )
        return

    lines = [
        f"📞 <b>SIP владельца группы</b>",
        f"👤 <code>{escape_html(owner.internal_id)}</code>\n",
    ]
    for sip in sips:
        icon = STATUS_ICONS.get(sip.status, "⚪")
        label = STATUS_LABELS.get(sip.status, sip.status.value)
        line = f"{icon} <code>{escape_html(sip.sip_number)}</code> — {label}"
        if sip.description:
            line += f" · {escape_html(sip.description[:40])}"
        lines.append(line)
    lines.append("\nЗаявка: <code>/err номер</code> (пример: <code>/err 100</code>)")
    await message.reply("\n".join(lines), parse_mode="HTML")
