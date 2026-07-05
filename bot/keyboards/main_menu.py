from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from bot.utils.menu_catalog import (
    BTN_ADMIN,
    BTN_ADMIN_HELP,
    BTN_BALANCE,
    BTN_HELP,
    BTN_GUIDES,
    BTN_MINI_APP,
    BTN_MY_ID,
    BTN_MY_SIPS,
    BTN_MY_TICKETS,
    BTN_PROFILE,
    BTN_REPORT,
    BTN_RULES,
    BTN_TOPUP,
)
from bot.utils.webapp import get_mini_app_url
from db.models.user import User, UserRole


def get_main_menu(user: User | None = None) -> ReplyKeyboardMarkup:
    """Главное меню: заявки → SIP → финансы → профиль → справка."""
    rows: list[list[KeyboardButton]] = [
        [KeyboardButton(text=BTN_REPORT)],
        [
            KeyboardButton(text=BTN_MY_SIPS),
            KeyboardButton(text=BTN_MY_TICKETS),
        ],
        [
            KeyboardButton(text=BTN_BALANCE),
            KeyboardButton(text=BTN_TOPUP),
        ],
        [
            KeyboardButton(text=BTN_PROFILE),
            KeyboardButton(text=BTN_MY_ID),
        ],
    ]

    mini_url = get_mini_app_url()
    if mini_url:
        rows.append([
            KeyboardButton(text=BTN_MINI_APP, web_app=WebAppInfo(url=mini_url)),
        ])

    rows.extend([
        [
            KeyboardButton(text=BTN_GUIDES),
            KeyboardButton(text=BTN_HELP),
        ],
        [
            KeyboardButton(text=BTN_RULES),
            KeyboardButton(text=BTN_ADMIN),
        ],
    ])

    if user and user.role in (UserRole.support, UserRole.admin, UserRole.superadmin):
        rows.append([KeyboardButton(text=BTN_ADMIN_HELP)])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        persistent=True,
        is_persistent=True,
        input_field_placeholder="Выберите действие в меню…",
    )
