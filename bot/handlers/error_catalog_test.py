from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.catalog.errors import CATEGORY_LABELS, ErrorCategory, get_preset, get_presets_for_category
from bot.filters.chat import apply_private_chat_filter
from bot.keyboards.error_types import (
    TEST_PREFIX,
    get_error_category_keyboard,
    get_error_presets_keyboard,
)
from bot.utils.formatting import escape_html
from bot.utils.menu_catalog import BTN_TEST_ERRORS
from bot.utils.test_mode import can_use_error_test_menu
from db.models.ticket import ErrorType
from db.models.user import User

router = apply_private_chat_filter(Router())

ERROR_TYPE_LABELS = {
    ErrorType.busy_here: "📵 Busy Here",
    ErrorType.no_registration: "❌ Нет регистрации",
    ErrorType.no_calls: "📞 Не проходят звонки",
    ErrorType.no_balance: "💳 Кончился баланс",
    ErrorType.sim_problem: "📱 Проблема с SIM",
    ErrorType.other: "💬 Другое",
}


def _access_denied_text() -> str:
    return (
        "⛔ Тестовый режим недоступен.\n\n"
        "Включите <code>TEST_MODE=true</code> в .env и используйте роль "
        "support / admin / superadmin."
    )


async def _open_test_menu(message: Message, user: User) -> None:
    if not can_use_error_test_menu(user):
        await message.answer(_access_denied_text(), parse_mode="HTML")
        return

    total = sum(len(get_presets_for_category(c)) for c in ErrorCategory)
    await message.answer(
        "🧪 <b>Тестовый режим — справочник ошибок</b>\n\n"
        f"Категорий: {len(ErrorCategory)}\n"
        f"Позиций в справочнике: {total}\n\n"
        "Заявка <b>не создаётся</b> — только просмотр меню и карточек ошибок.",
        parse_mode="HTML",
        reply_markup=get_error_category_keyboard(prefix=TEST_PREFIX),
    )


@router.message(F.text.in_({BTN_TEST_ERRORS}))
@router.message(Command("test_errors"))
async def cmd_test_errors(message: Message, user: User):
    await _open_test_menu(message, user)


@router.callback_query(F.data == f"{TEST_PREFIX}:close")
async def test_close(callback: CallbackQuery, user: User):
    if not can_use_error_test_menu(user):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    await callback.message.edit_text("🧪 Тестовый режим закрыт.")
    await callback.answer()


@router.callback_query(F.data == f"{TEST_PREFIX}:back")
async def test_back_categories(callback: CallbackQuery, user: User):
    if not can_use_error_test_menu(user):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    total = sum(len(get_presets_for_category(c)) for c in ErrorCategory)
    await callback.message.edit_text(
        "🧪 <b>Тестовый режим — справочник ошибок</b>\n\n"
        f"Позиций в справочнике: {total}\n"
        "Выберите категорию:",
        parse_mode="HTML",
        reply_markup=get_error_category_keyboard(prefix=TEST_PREFIX),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{TEST_PREFIX}:cat:"))
async def test_category_selected(callback: CallbackQuery, user: User):
    if not can_use_error_test_menu(user):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return

    category = ErrorCategory(callback.data.split(":")[2])
    presets = get_presets_for_category(category)
    await callback.message.edit_text(
        f"🧪 {CATEGORY_LABELS[category]}\n\n"
        f"Пунктов: {len(presets)}\n"
        "Выберите ошибку для просмотра карточки:",
        parse_mode="HTML",
        reply_markup=get_error_presets_keyboard(category, page=0, prefix=TEST_PREFIX),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{TEST_PREFIX}:page:"))
async def test_preset_page(callback: CallbackQuery, user: User):
    if not can_use_error_test_menu(user):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return

    parts = callback.data.split(":")
    category = ErrorCategory(parts[2])
    page = int(parts[3])
    presets = get_presets_for_category(category)
    await callback.message.edit_text(
        f"🧪 {CATEGORY_LABELS[category]}\n\n"
        f"Пунктов: {len(presets)}\n"
        "Выберите ошибку для просмотра карточки:",
        parse_mode="HTML",
        reply_markup=get_error_presets_keyboard(category, page=page, prefix=TEST_PREFIX),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{TEST_PREFIX}:preset:"))
async def test_preset_preview(callback: CallbackQuery, user: User):
    if not can_use_error_test_menu(user):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return

    preset_id = callback.data.split(":")[2]
    preset = get_preset(preset_id)
    if not preset:
        await callback.answer("⚠️ Не найдено.", show_alert=True)
        return

    error_label = f"{CATEGORY_LABELS[preset.category]} → {preset.title}"
    db_label = ERROR_TYPE_LABELS.get(preset.error_type, preset.error_type.value)

    text = (
        "🧪 <b>Предпросмотр карточки ошибки</b>\n\n"
        f"📂 Категория: {CATEGORY_LABELS[preset.category]}\n"
        f"🏷 Кнопка: {escape_html(preset.button)}\n"
        f"⚠️ Заголовок: {escape_html(preset.title)}\n"
        f"🗂 Тип в БД: {db_label}\n\n"
        f"📝 Описание заявки:\n{escape_html(preset.description)}\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "<i>Так увидит support / суперадмин:</i>\n\n"
        f"⚠️ Тип ошибки: {escape_html(error_label)}\n"
        f"📝 Описание: {escape_html(preset.description)}"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.button(
        text="◀️ К списку",
        callback_data=f"{TEST_PREFIX}:cat:{preset.category.value}",
    )
    builder.button(text="📂 К категориям", callback_data=f"{TEST_PREFIX}:back")
    builder.button(text="❌ Закрыть", callback_data=f"{TEST_PREFIX}:close")
    builder.adjust(1)

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()
