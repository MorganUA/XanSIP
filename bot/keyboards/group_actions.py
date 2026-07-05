from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

PREFIX = "grp"


def get_group_help_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Активные заявки", callback_data=f"{PREFIX}:status")
    builder.button(text="📞 SIP владельца", callback_data=f"{PREFIX}:sips")
    builder.button(text="ℹ️ Справка", callback_data=f"{PREFIX}:help")
    builder.adjust(2, 1)
    return builder.as_markup()
