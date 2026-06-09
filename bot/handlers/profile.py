from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from db.models.user import User
from bot.keyboards.main_menu import get_main_menu

router = Router()

ROLE_LABELS = {
    "user": "👤 Пользователь",
    "support": "🛠 Поддержка",
    "admin": "👑 Администратор",
    "superadmin": "⚡️ Суперадмин",
}


@router.message(F.text == "👤 Профиль")
@router.message(Command("profile"))
async def show_profile(message: Message, user: User):
    role_label = ROLE_LABELS.get(user.role.value, user.role.value)
    username_str = f"@{user.username}" if user.username else "не указан"
    name_parts = filter(None, [user.first_name, user.last_name])
    full_name = " ".join(name_parts) or "не указано"

    text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"🆔 Внутренний ID: <code>{user.internal_id}</code>\n"
        f"📱 Telegram ID: <code>{user.telegram_id}</code>\n"
        f"👤 Имя: {full_name}\n"
        f"🔗 Username: {username_str}\n"
        f"🎭 Роль: {role_label}\n"
        f"📅 Зарегистрирован: {user.created_at.strftime('%d.%m.%Y')}"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu())


@router.message(F.text == "🆔 Мой ID")
@router.message(Command("myid"))
async def show_id(message: Message, user: User):
    await message.answer(
        f"🆔 Ваш внутренний ID:\n\n"
        f"<code>{user.internal_id}</code>\n\n"
        f"Сообщите этот ID администратору для заказа SIP-номеров.",
        parse_mode="HTML",
    )
