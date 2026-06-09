from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models.ticket import Ticket, ErrorType
from db.models.user import User
from db.models.sip_account import SipAccount
from db.models.group import Group
from bot.keyboards.support_actions import get_support_action_keyboard
from bot.config import settings

ERROR_TYPE_LABELS = {
    ErrorType.busy_here: "📵 Busy Here",
    ErrorType.no_registration: "❌ Нет регистрации",
    ErrorType.no_calls: "📞 Не проходят звонки",
    ErrorType.no_balance: "💳 Кончился баланс",
    ErrorType.sim_problem: "📱 Проблема с SIM",
    ErrorType.other: "💬 Другое",
}


async def notify_support_new_ticket(
    bot: Bot,
    ticket: Ticket,
    user: User,
    sip: SipAccount | None,
    group: Group | None = None,
) -> int | None:
    username_str = f"@{user.username}" if user.username else "нет username"
    sip_str = f"<code>{sip.sip_number}</code>" if sip else "не указан"
    error_label = ERROR_TYPE_LABELS.get(ticket.error_type, ticket.error_type.value)
    source_str = f"👥 Группа: {group.group_name}" if group else "💬 Личный чат"

    text = (
        f"🚨 <b>Новая заявка #{ticket.id}</b>\n\n"
        f"👤 Пользователь: {user.first_name or ''} {username_str}\n"
        f"🆔 ID клиента: <code>{user.internal_id}</code>\n"
        f"📞 SIP: {sip_str}\n"
        f"⚠️ Тип ошибки: {error_label}\n"
        f"📝 Описание: {ticket.description}\n"
        f"📍 Источник: {source_str}\n"
        f"🕐 Время: {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"📊 Статус: 🆕 Новая"
    )

    try:
        msg = await bot.send_message(
            chat_id=settings.support_group_id,
            text=text,
            parse_mode="HTML",
            reply_markup=get_support_action_keyboard(ticket.id),
        )
        return msg.message_id
    except Exception as e:
        print(f"[notify_support] Ошибка: {e}")
        return None


async def notify_user_ticket_update(
    bot: Bot,
    user: User,
    ticket: Ticket,
    status_text: str,
    group: Group | None = None,
) -> None:
    text = (
        f"📋 <b>Обновление по заявке #{ticket.id}</b>\n\n"
        f"{status_text}"
    )
    # Уведомляем в личку
    try:
        await bot.send_message(
            chat_id=user.telegram_id,
            text=text,
            parse_mode="HTML",
        )
    except Exception as e:
        print(f"[notify_user] Ошибка личка {user.telegram_id}: {e}")

    # Уведомляем в группу если тикет оттуда
    if group and group.is_approved:
        try:
            await bot.send_message(
                chat_id=group.telegram_group_id,
                text=text,
                parse_mode="HTML",
            )
        except Exception as e:
            print(f"[notify_group] Ошибка группа {group.telegram_group_id}: {e}")


async def notify_admin_new_group(
    bot: Bot,
    group_telegram_id: int,
    group_name: str | None,
    added_by: User,
) -> None:
    """Уведомляет админа о новой группе которая ждёт одобрения."""
    username_str = f"@{added_by.username}" if added_by.username else added_by.first_name
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
        f"📛 Название: {group_name or 'без названия'}\n"
        f"🆔 ID группы: <code>{group_telegram_id}</code>\n"
        f"👤 Добавил: {username_str}\n"
        f"🆔 ID клиента: <code>{added_by.internal_id}</code>"
    )

    try:
        await bot.send_message(
            chat_id=settings.superadmin_telegram_id,
            text=text,
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
        )
    except Exception as e:
        print(f"[notify_admin_group] Ошибка: {e}")
