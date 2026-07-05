import logging

from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.support_actions import get_support_action_keyboard
from bot.services.notification_config import get_notification_config
from bot.utils.formatting import escape_html
from bot.utils.telegram_send import send_message_safe
from db.models.group import Group
from db.models.sip_account import SipAccount
from db.models.ticket import ErrorType, Ticket
from db.models.user import User

from bot.catalog.error_labels import ERROR_TYPE_LABELS

logger = logging.getLogger(__name__)


def _user_label(user: User) -> str:
    name = escape_html(user.first_name or "")
    username = f"@{escape_html(user.username)}" if user.username else "нет username"
    return f"{name} {username}".strip()


def _format_ticket_message(
    ticket: Ticket,
    user: User,
    sip: SipAccount | None,
    group: Group | None,
    *,
    error_label: str | None = None,
) -> str:
    sip_str = f"<code>{escape_html(sip.sip_number)}</code>" if sip else "не указан"
    label = error_label or ERROR_TYPE_LABELS.get(ticket.error_type, ticket.error_type.value)
    source_str = (
        f"👥 Группа: {escape_html(group.group_name or 'без названия')}"
        if group
        else "💬 Личный чат"
    )
    return (
        f"🚨 <b>Новая заявка #{ticket.id}</b>\n\n"
        f"👤 Пользователь: {_user_label(user)}\n"
        f"🆔 ID клиента: <code>{escape_html(user.internal_id)}</code>\n"
        f"📞 SIP: {sip_str}\n"
        f"⚠️ Тип ошибки: {escape_html(label)}\n"
        f"📝 Описание: {escape_html(ticket.description)}\n"
        f"📍 Источник: {source_str}\n"
        f"🕐 Время: {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"📊 Статус: 🆕 Новая"
    )


async def _send_to_chats(
    bot: Bot,
    session: AsyncSession | None,
    chat_ids: list[int],
    text: str,
    *,
    reply_markup=None,
    label: str,
) -> list[tuple[int, int]]:
    delivered: list[tuple[int, int]] = []
    for chat_id in chat_ids:
        try:
            result = await send_message_safe(
                bot,
                chat_id,
                text,
                reply_markup=reply_markup,
                session=session,
            )
            if result:
                delivered.append(result)
        except Exception:
            logger.exception("Failed to notify %s chat %s", label, chat_id)
    return delivered


async def notify_support_new_ticket(
    bot: Bot,
    ticket: Ticket,
    user: User,
    sip: SipAccount | None,
    group: Group | None = None,
    *,
    error_label: str | None = None,
    session: AsyncSession | None = None,
) -> int | None:
    config = await get_notification_config(session)
    events = config["events"].get("ticket_new", {})
    text = _format_ticket_message(ticket, user, sip, group, error_label=error_label)
    markup = get_support_action_keyboard(ticket.id)
    support_ids = set(config.get("support_chat_ids", []))

    delivered: list[tuple[int, int]] = []
    if events.get("support_chats", True):
        delivered += await _send_to_chats(
            bot, session, config.get("support_chat_ids", []),
            text, reply_markup=markup, label="support",
        )
    if events.get("admin_chats", True):
        delivered += await _send_to_chats(
            bot, session, config.get("admin_chat_ids", []),
            text, reply_markup=markup, label="admin",
        )

    if not delivered:
        return None

    for chat_id, msg_id in delivered:
        if chat_id in support_ids:
            return msg_id
    return delivered[0][1]


async def notify_user_ticket_update(
    bot: Bot,
    user: User,
    ticket: Ticket,
    status_text: str,
    group: Group | None = None,
    *,
    session: AsyncSession | None = None,
    event: str = "ticket_status",
) -> bool:
    config = await get_notification_config(session)
    events = config["events"].get(event, config["events"].get("ticket_status", {}))
    text = f"📋 <b>Обновление по заявке #{ticket.id}</b>\n\n{status_text}"
    delivered = False

    if events.get("user_dm", True):
        try:
            await send_message_safe(bot, user.telegram_id, text, session=session)
            delivered = True
        except Exception:
            logger.exception(
                "Failed to notify user %s about ticket #%s",
                user.telegram_id,
                ticket.id,
            )

    if group and group.is_approved and events.get("source_group", True):
        try:
            await send_message_safe(
                bot, group.telegram_group_id, text, session=session,
            )
            delivered = True
        except Exception:
            logger.exception(
                "Failed to notify group %s about ticket #%s",
                group.telegram_group_id,
                ticket.id,
            )

    return delivered


async def notify_admin_new_group(
    bot: Bot,
    group_telegram_id: int,
    group_name: str | None,
    added_by: User,
    *,
    session: AsyncSession | None = None,
) -> bool:
    config = await get_notification_config(session)
    events = config["events"].get("group_pending", {})

    username_str = (
        f"@{escape_html(added_by.username)}"
        if added_by.username
        else escape_html(added_by.first_name or "неизвестно")
    )
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Одобрить",
        callback_data=f"group:approve:{group_telegram_id}",
    )
    builder.button(
        text="❌ Отклонить",
        callback_data=f"group:reject:{group_telegram_id}",
    )
    builder.adjust(2)

    text = (
        f"👥 <b>Новая группа ждёт одобрения</b>\n\n"
        f"📛 Название: {escape_html(group_name or 'без названия')}\n"
        f"🆔 ID группы: <code>{group_telegram_id}</code>\n"
        f"👤 Добавил: {username_str}\n"
        f"🆔 ID клиента: <code>{escape_html(added_by.internal_id)}</code>\n\n"
        f"После одобрения назначьте владельца: "
        f"<code>/set_group_owner {group_telegram_id} telegram_id</code>"
    )
    markup = builder.as_markup()

    chat_ids: list[int] = []
    if events.get("support_chats", True):
        chat_ids.extend(config.get("support_chat_ids", []))
    if events.get("admin_chats", True):
        chat_ids.extend(config.get("admin_chat_ids", []))

    delivered = await _send_to_chats(
        bot, session, list(dict.fromkeys(chat_ids)),
        text, reply_markup=markup, label="group_pending",
    )
    return bool(delivered)
