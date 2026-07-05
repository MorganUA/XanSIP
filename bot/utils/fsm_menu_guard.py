"""Отмена FSM при нажатии reply-кнопки меню и переход к нужному разделу."""

from __future__ import annotations

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.main_menu import get_main_menu
from bot.utils.menu_catalog import is_private_menu_button
from bot.utils.menu_dispatch import dispatch_menu_button
from bot.utils.quick_errors import OTHER_ERROR_BUTTON, quick_error_button_texts
from db.models.user import User


def _is_menu_navigation(text: str | None) -> bool:
    if not text:
        return False
    t = text.strip()
    return t in quick_error_button_texts() or t == OTHER_ERROR_BUTTON or is_private_menu_button(t)


async def cancel_fsm_for_menu_button(
    message: Message,
    user: User,
    state: FSMContext,
    session: AsyncSession,
    *,
    redis: Redis | None = None,
    cancel_note: str = "Текущее действие отменено.",
) -> bool:
    """
    Если пользователь нажал кнопку меню во время FSM — сбросить состояние
    и выполнить действие кнопки. True — если обработано.
    """
    if not _is_menu_navigation(message.text):
        return False

    await state.clear()
    dispatched = await dispatch_menu_button(
        message, user, session, state=state, redis=redis,
    )
    if dispatched:
        return True

    await message.answer(
        f"❌ {cancel_note}\n\nПовторите выбор в меню.",
        reply_markup=get_main_menu(user),
    )
    return True
