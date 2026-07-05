from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.catalog.group_errors import (
    GROUP_ERROR_PRESETS,
    MAIN_PRESET_IDS,
    SUBMENU_PRESET_IDS,
)

PREFIX = "perr"


def get_private_error_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for preset_id in MAIN_PRESET_IDS:
        preset = GROUP_ERROR_PRESETS[preset_id]
        builder.button(text=preset.button, callback_data=f"{PREFIX}:m:{preset_id}")
    builder.button(text="📋 Ещё проблемы ▶", callback_data=f"{PREFIX}:more")
    builder.button(text="📚 Полный справочник", callback_data=f"{PREFIX}:catalog")
    builder.button(text="❌ Отмена", callback_data=f"{PREFIX}:cancel")
    builder.adjust(1)
    return builder.as_markup()


def get_private_submenu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for preset_id in SUBMENU_PRESET_IDS:
        preset = GROUP_ERROR_PRESETS[preset_id]
        builder.button(text=preset.button, callback_data=f"{PREFIX}:s:{preset_id}")
    builder.button(text="◀️ Назад", callback_data=f"{PREFIX}:back")
    builder.button(text="❌ Отмена", callback_data=f"{PREFIX}:cancel")
    builder.adjust(2, 2, 2, 1, 1)
    return builder.as_markup()
