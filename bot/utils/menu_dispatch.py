"""Повторная маршрутизация reply-кнопок меню (например, после отмены FSM)."""

from __future__ import annotations

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.utils.menu_catalog import (
    TEXTS_ADMIN,
    TEXTS_ADMIN_HELP,
    TEXTS_BALANCE,
    TEXTS_GUIDES,
    TEXTS_HELP,
    TEXTS_MY_ID,
    TEXTS_MY_SIPS,
    TEXTS_MY_TICKETS,
    TEXTS_PROFILE,
    TEXTS_REPORT,
    TEXTS_RULES,
    TEXTS_TOPUP,
    BTN_TEST_ERRORS,
)
from bot.utils.quick_errors import OTHER_ERROR_BUTTON, preset_id_from_button, quick_error_button_texts
from db.models.user import User


async def dispatch_menu_button(
    message: Message,
    user: User,
    session: AsyncSession,
    *,
    state: FSMContext | None = None,
    redis: Redis | None = None,
) -> bool:
    """Обработать текст reply-кнопки меню. True — если обработано."""
    text = (message.text or "").strip()
    if not text:
        return False

    if text in TEXTS_REPORT:
        from bot.handlers.tickets import open_report_menu

        await open_report_menu(message, user)
        return True

    if text in quick_error_button_texts() and redis and state:
        from bot.handlers.tickets import quick_error_from_menu

        await quick_error_from_menu(message, user, state, session, redis)
        return True

    if text == OTHER_ERROR_BUTTON:
        from bot.handlers.tickets import start_ticket_fsm

        await start_ticket_fsm(message, user, state, session)
        return True

    if text in TEXTS_MY_SIPS:
        from bot.handlers.sip import show_my_sip

        await show_my_sip(message, user, session)
        return True

    if text in TEXTS_MY_TICKETS:
        from bot.handlers.my_tickets import cmd_my_tickets

        await cmd_my_tickets(message, user, session)
        return True

    if text in TEXTS_BALANCE:
        from bot.handlers.finance import show_balance

        await show_balance(message, user, session)
        return True

    if text in TEXTS_TOPUP:
        from bot.handlers.finance import start_topup

        await start_topup(message, user, state, session)
        return True

    if text in TEXTS_PROFILE:
        from bot.handlers.profile import show_profile

        await show_profile(message, user, session)
        return True

    if text in TEXTS_MY_ID:
        from bot.handlers.profile import show_id

        await show_id(message, user)
        return True

    if text in TEXTS_GUIDES:
        from bot.handlers.guides import cmd_guides

        await cmd_guides(message, user)
        return True

    if text in TEXTS_HELP:
        from bot.handlers.admin_contact import cmd_help

        await cmd_help(message, user)
        return True

    if text in TEXTS_RULES:
        from bot.handlers.rules import show_rules

        await show_rules(message, user)
        return True

    if text in TEXTS_ADMIN:
        from bot.handlers.admin_contact import admin_contact

        await admin_contact(message, user)
        return True

    if text in TEXTS_ADMIN_HELP:
        from bot.handlers.admin_commands import admin_help

        await admin_help(message, user)
        return True

    if text == BTN_TEST_ERRORS:
        from bot.handlers.error_catalog_test import cmd_test_errors

        await cmd_test_errors(message, user)
        return True

    return False
