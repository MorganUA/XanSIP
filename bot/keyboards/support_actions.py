from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_support_action_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🔧 Взять в работу",
        callback_data=f"ticket:take:{ticket_id}",
    )
    builder.button(
        text="✅ Решено",
        callback_data=f"ticket:resolve:{ticket_id}",
    )
    builder.button(
        text="❓ Нужна доп. информация",
        callback_data=f"ticket:waiting:{ticket_id}",
    )
    builder.button(
        text="❌ Отклонить",
        callback_data=f"ticket:reject:{ticket_id}",
    )
    builder.adjust(1)
    return builder.as_markup()


def get_support_taken_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    """Кнопки после того как тикет взят в работу."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Решено",
        callback_data=f"ticket:resolve:{ticket_id}",
    )
    builder.button(
        text="❓ Нужна доп. информация",
        callback_data=f"ticket:waiting:{ticket_id}",
    )
    builder.button(
        text="❌ Отклонить",
        callback_data=f"ticket:reject:{ticket_id}",
    )
    builder.adjust(1)
    return builder.as_markup()
