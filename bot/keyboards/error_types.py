from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models.ticket import ErrorType


ERROR_TYPE_LABELS = {
    ErrorType.busy_here: "📵 Busy Here",
    ErrorType.no_registration: "❌ Нет регистрации",
    ErrorType.no_calls: "📞 Не проходят звонки",
    ErrorType.no_balance: "💳 Кончился баланс",
    ErrorType.sim_problem: "📱 Проблема с SIM",
    ErrorType.other: "💬 Другое",
}


def get_error_type_keyboard(sip_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for error_type, label in ERROR_TYPE_LABELS.items():
        builder.button(
            text=label,
            callback_data=f"error:type:{sip_id}:{error_type.value}",
        )
    builder.button(text="❌ Отмена", callback_data="ticket:cancel")
    builder.adjust(2)
    return builder.as_markup()
