"""Руководства по эксплуатации — бот."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.filters.chat import apply_private_chat_filter
from bot.keyboards.main_menu import get_main_menu
from bot.utils.menu_catalog import BTN_GUIDES, TEXTS_GUIDES
from bot.utils.menu_text import web_crm_url_line
from db.models.user import User, UserRole
from services.operation_guides import (
    AUDIENCES,
    format_guide_html,
    get_guide_by_id,
    guides_for_audience,
    split_telegram_text,
)

router = apply_private_chat_filter(Router())

PREFIX = "opguide"


def _audiences_for_user(user: User) -> list[str]:
    keys = ["workflow", "user", "group_owner"]
    if user.role in (UserRole.support, UserRole.admin, UserRole.superadmin):
        keys.append("admin")
    return keys


def _audience_keyboard(user: User):
    builder = InlineKeyboardBuilder()
    for key in _audiences_for_user(user):
        meta = AUDIENCES[key]
        builder.button(
            text=f"{meta['icon']} {meta['label']}",
            callback_data=f"{PREFIX}:aud:{key}",
        )
    builder.adjust(1)
    return builder.as_markup()


def _guides_list_keyboard(audience: str):
    builder = InlineKeyboardBuilder()
    for g in guides_for_audience(audience):
        builder.button(text=g["title"], callback_data=f"{PREFIX}:g:{g['id']}")
    builder.button(text="← К аудиториям", callback_data=f"{PREFIX}:back")
    builder.adjust(1)
    return builder.as_markup()


async def _send_guides_intro(message: Message, user: User) -> None:
    web = web_crm_url_line()
    text = (
        "<b>📖 Руководства по эксплуатации</b>\n\n"
        "Выберите раздел:\n"
        "• <b>Маршрут продукта</b> — порядок работы для максимальной пользы\n"
        "• <b>Пользователь</b> — личный чат, заявки, USDT\n"
        "• <b>Владелец группы</b> — колл-центр, /err\n"
    )
    if user.role in (UserRole.support, UserRole.admin, UserRole.superadmin):
        text += "• <b>Администратор</b> — Web CRM, модерация\n"
    if web:
        text += f"\nПолная версия в Web CRM → 📖 Руководства\n{web}"
    await message.answer(text, reply_markup=_audience_keyboard(user), parse_mode="HTML")


@router.message(F.text.in_(TEXTS_GUIDES))
@router.message(Command("guides"))
async def cmd_guides(message: Message, user: User):
    await _send_guides_intro(message, user)


@router.callback_query(F.data.startswith(f"{PREFIX}:"))
async def guides_callback(callback: CallbackQuery, user: User):
    parts = callback.data.split(":")
    action = parts[1]

    if action == "back":
        await callback.message.edit_text(
            "<b>📖 Руководства</b>\n\nВыберите аудиторию:",
            reply_markup=_audience_keyboard(user),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    if action == "aud" and len(parts) >= 3:
        audience = parts[2]
        if audience not in _audiences_for_user(user):
            await callback.answer("Нет доступа", show_alert=True)
            return
        meta = AUDIENCES[audience]
        await callback.message.edit_text(
            f"<b>{meta['icon']} {meta['label']}</b>\n{meta['description']}\n\nВыберите тему:",
            reply_markup=_guides_list_keyboard(audience),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    if action == "g" and len(parts) >= 3:
        guide_id = parts[2]
        guide = get_guide_by_id(guide_id)
        if not guide:
            await callback.answer("Не найдено", show_alert=True)
            return
        if guide["audience"] not in _audiences_for_user(user):
            await callback.answer("Нет доступа", show_alert=True)
            return
        html = format_guide_html(guide)
        chunks = split_telegram_text(html)
        await callback.message.edit_reply_markup(reply_markup=None)
        for i, chunk in enumerate(chunks):
            if i == len(chunks) - 1:
                builder = InlineKeyboardBuilder()
                builder.button(
                    text="← К списку тем",
                    callback_data=f"{PREFIX}:aud:{guide['audience']}",
                )
                builder.button(text="← К аудиториям", callback_data=f"{PREFIX}:back")
                builder.adjust(1)
                await callback.message.answer(chunk, parse_mode="HTML", reply_markup=builder.as_markup())
            else:
                await callback.message.answer(chunk, parse_mode="HTML")
        await callback.answer()
        return

    await callback.answer()
