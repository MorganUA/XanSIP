from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="👤 Профиль"),
                KeyboardButton(text="🆔 Мой ID"),
            ],
            [
                KeyboardButton(text="📞 Мои SIP"),
                KeyboardButton(text="🚨 Сообщить об ошибке"),
            ],
            [
                KeyboardButton(text="👨‍💼 Связь с админом"),
                KeyboardButton(text="📋 Правила"),
            ],
        ],
        resize_keyboard=True,
        persistent=True,
    )
