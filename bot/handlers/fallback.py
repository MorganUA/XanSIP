from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters.chat import apply_private_chat_filter
from bot.keyboards.main_menu import get_main_menu
from bot.utils.menu_catalog import (
    BTN_HELP,
    BTN_MY_TICKETS,
    BTN_REPORT,
    is_private_menu_button,
)
from bot.utils.menu_dispatch import dispatch_menu_button
from bot.utils.quick_errors import OTHER_ERROR_BUTTON, quick_error_button_texts
from db.models.user import User

router = apply_private_chat_filter(Router())

_quick = " · ".join(quick_error_button_texts())


@router.message(F.text)
async def private_unknown_message(
    message: Message,
    user: User,
    session: AsyncSession,
    state: FSMContext,
    redis: Redis,
):
    if is_private_menu_button(message.text):
        if await dispatch_menu_button(message, user, session, state=state, redis=redis):
            return
    await message.answer(
        "Команда не распознана.\n\n"
        f"Используйте кнопки меню или <b>{BTN_HELP}</b> (/help).\n"
        f"Заявка: <b>{BTN_REPORT}</b> или {_quick}.\n"
        f"Каталог ошибок: <b>{OTHER_ERROR_BUTTON}</b>.\n"
        f"Статус: <b>{BTN_MY_TICKETS}</b>.",
        parse_mode="HTML",
        reply_markup=get_main_menu(user),
    )
