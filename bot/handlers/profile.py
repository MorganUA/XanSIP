from aiogram import F, Router
from aiogram.types import Message
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import User, UserRole
from services.finance_service import get_user_balance
from bot.filters.chat import apply_private_chat_filter
from bot.keyboards.main_menu import get_main_menu
from bot.utils.menu_catalog import (
    BTN_ADMIN_HELP,
    BTN_MY_ID,
    BTN_MY_TICKETS,
    BTN_PROFILE,
    TEXTS_MY_ID,
    TEXTS_PROFILE,
)
from bot.utils.ticket_status import ACTIVE_STATUSES
from db.repositories.ticket_repo import TicketRepository

router = apply_private_chat_filter(Router())

ROLE_LABELS = {
    "user": "Пользователь",
    "support": "Поддержка",
    "admin": "Администратор",
    "superadmin": "Суперадмин",
}


@router.message(F.text.in_(TEXTS_PROFILE))
@router.message(Command("profile"))
async def show_profile(message: Message, user: User, session: AsyncSession):
    role_label = ROLE_LABELS.get(user.role.value, user.role.value)
    username_str = f"@{user.username}" if user.username else "не указан"
    name_parts = filter(None, [user.first_name, user.last_name])
    full_name = " ".join(name_parts) or "не указано"

    ticket_repo = TicketRepository(session)
    tickets = await ticket_repo.get_by_user_id(user.id, limit=20)
    active_count = sum(1 for t in tickets if t.status in ACTIVE_STATUSES)
    balance = await get_user_balance(session, user.id)

    text = (
        "<b>Профиль</b>\n\n"
        f"ID: <code>{user.internal_id}</code>\n"
        f"Telegram: <code>{user.telegram_id}</code>\n"
        f"Имя: {full_name}\n"
        f"Username: {username_str}\n"
        f"Роль: {role_label}\n"
        f"Баланс: <code>{balance}</code> USDT\n"
        f"Регистрация: {user.created_at.strftime('%d.%m.%Y')}\n"
        f"Активных заявок: <b>{active_count}</b> — см. <b>{BTN_MY_TICKETS}</b>"
    )
    if user.role == UserRole.support:
        text += (
            "\n\nОбработка заявок — чат поддержки или Web CRM (Колл-центр)."
        )
    elif user.role in (UserRole.admin, UserRole.superadmin):
        text += f"\n\nПерсонал: <b>{BTN_ADMIN_HELP}</b> или /admin_help"
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu(user))


@router.message(F.text.in_(TEXTS_MY_ID))
@router.message(Command("myid"))
async def show_id(message: Message, user: User):
    await message.answer(
        "<b>Мой ID</b>\n\n"
        f"<code>{user.internal_id}</code>\n\n"
        "Сообщите этот ID поддержке при заказе SIP или пополнении.",
        parse_mode="HTML",
        reply_markup=get_main_menu(user),
    )
