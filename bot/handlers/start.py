from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from db.models.user import User
from bot.keyboards.main_menu import get_main_menu

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, user: User):
    name = user.first_name or user.username or "друг"
    await message.answer(
        f"👋 Привет, {name}!\n\n"
        f"Добро пожаловать в SIP Manager Bot.\n"
        f"Ваш внутренний ID: <code>{user.internal_id}</code>\n\n"
        f"Используйте меню ниже для навигации.",
        reply_markup=get_main_menu(),
        parse_mode="HTML",
    )
