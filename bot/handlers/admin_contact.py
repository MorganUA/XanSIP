from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import settings
from bot.filters.chat import apply_private_chat_filter
from bot.keyboards.main_menu import get_main_menu
from bot.utils.menu_text import web_crm_url_line
from bot.utils.menu_catalog import (
    BTN_ADMIN,
    BTN_BALANCE,
    BTN_GUIDES,
    BTN_HELP,
    BTN_MINI_APP,
    BTN_MY_ID,
    BTN_MY_SIPS,
    BTN_MY_TICKETS,
    BTN_PROFILE,
    BTN_REPORT,
    BTN_RULES,
    BTN_TOPUP,
    TEXTS_ADMIN,
    TEXTS_HELP,
)
from bot.utils.webapp import get_mini_app_url
from db.models.user import User

router = apply_private_chat_filter(Router())


def _admin_username() -> str:
    admin = settings.admin_username
    return admin if admin.startswith("@") else f"@{admin}"


def _admin_contact_text() -> str:
    return (
        "<b>Поддержка</b>\n\n"
        f"Заказ SIP, подключение, оплата — {_admin_username()}\n\n"
        f"Укажите ID из раздела <b>{BTN_MY_ID}</b> при обращении."
    )


def _help_text() -> str:
    mini = (
        f"• <b>{BTN_MINI_APP}</b> — веб-кабинет (SIP, заявки)\n"
        if get_mini_app_url()
        else ""
    )
    web = web_crm_url_line()
    return (
        "<b>Справка · личный чат</b>\n\n"
        "<b>Заявки (Web CRM → Колл-центр)</b>\n"
        f"• <b>{BTN_REPORT}</b> — выбор типа проблемы\n"
        f"• {BTN_MY_SIPS} · {BTN_MY_TICKETS}\n\n"
        "<b>Финансы (Web CRM → Финансы)</b>\n"
        f"• {BTN_BALANCE} · {BTN_TOPUP}\n\n"
        "<b>Аккаунт</b>\n"
        f"• <b>{BTN_PROFILE}</b> · <b>{BTN_MY_ID}</b>\n"
        f"• <b>{BTN_ADMIN}</b> — связь с поддержкой\n"
        f"• <b>{BTN_RULES}</b> — правила сервиса\n"
        f"• <b>{BTN_GUIDES}</b> — руководства (/guides)\n"
        + (mini + "\n" if mini else "")
        + "<b>Web CRM (администраторы)</b>\n"
        "• roof — главный суперадмин (WEB_ADMIN_USERNAME)\n"
        "• admin01–admin05 — привилегированные\n"
        "• support01–support05 — операторы колл-центра\n"
        "• Подробно: /guides → Администратор → «Учётные записи Web CRM»\n"
        + "<b>Команды</b>\n"
        "/start · /help · /guides · /profile · /myid · /mysip · /tickets\n"
        "/balance · /deposit · /rules · /admin · /err SIP описание\n"
        "/admin_help — для поддержки и администраторов\n\n"
        "<b>Группа колл-центра</b>\n"
        "<code>/err номер_sip</code> → кнопки проблем\n"
        "<code>/status</code> · <code>/sips</code> · /help\n\n"
        f"Администратор: {_admin_username()}"
        + (f"\n{web.strip()}" if web else "")
    )


@router.message(F.text.in_(TEXTS_ADMIN))
@router.message(Command("admin"))
async def admin_contact(message: Message, user: User):
    await message.answer(
        _admin_contact_text(),
        parse_mode="HTML",
        reply_markup=get_main_menu(user),
    )


@router.message(F.text.in_(TEXTS_HELP))
@router.message(Command("help"))
async def cmd_help(message: Message, user: User):
    await message.answer(
        _help_text(),
        parse_mode="HTML",
        reply_markup=get_main_menu(user),
    )
