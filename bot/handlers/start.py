from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.filters.chat import apply_private_chat_filter
from bot.keyboards.main_menu import get_main_menu
from bot.utils.menu_catalog import (
    BTN_BALANCE,
    BTN_ADMIN_HELP,
    BTN_GUIDES,
    BTN_HELP,
    BTN_MINI_APP,
    BTN_MY_SIPS,
    BTN_MY_TICKETS,
    BTN_REPORT,
    BTN_TOPUP,
)
from bot.utils.menu_text import web_crm_url_line
from bot.utils.webapp import get_mini_app_url
from db.models.user import User, UserRole

router = apply_private_chat_filter(Router())


@router.message(CommandStart())
async def cmd_start(message: Message, user: User):
    name = user.first_name or user.username or "коллега"
    mini_line = (
        f"• <b>{BTN_MINI_APP}</b> — SIP, заявки, быстрые ошибки\n"
        if get_mini_app_url()
        else ""
    )
    lines = [
        "<b>SIP CRM</b>",
        f"Здравствуйте, {name}.",
        "",
        f"ID: <code>{user.internal_id}</code>",
        "",
        "<b>Личный чат</b>",
        f"• <b>{BTN_REPORT}</b> — главное действие",
        f"• {BTN_MY_SIPS} · {BTN_MY_TICKETS}",
        f"• {BTN_BALANCE} · {BTN_TOPUP}",
        mini_line.rstrip(),
        f"• {BTN_GUIDES} — подробные инструкции\n"
        f"• {BTN_HELP} — команды",
        "",
        "<b>Группа колл-центра</b>",
        "• <code>/err номер_sip</code> → тип проблемы",
        "• <code>/status</code> · <code>/sips</code>",
    ]
    if user.role == UserRole.support:
        lines.extend(["", f"Персонал: <b>{BTN_ADMIN_HELP}</b> · Web CRM (колл-центр)"])
    elif user.role in (UserRole.admin, UserRole.superadmin):
        lines.extend(["", f"Администратор: <b>{BTN_ADMIN_HELP}</b> · Web CRM"])
    web = web_crm_url_line()
    if web:
        lines.append(web)
    await message.answer(
        "\n".join(line for line in lines if line),
        reply_markup=get_main_menu(user),
        parse_mode="HTML",
    )
