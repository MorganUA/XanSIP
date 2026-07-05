"""Единый каталог кнопок меню — согласован с Web CRM (Service Desk · SIP · Финансы)."""

from bot.catalog.group_errors import GROUP_ERROR_PRESETS, MAIN_PRESET_IDS
from bot.utils.quick_errors import OTHER_ERROR_BUTTON

# —— Reply-клавиатура: эмодзи только на главных пунктах ——
BTN_REPORT = "🚨 Сообщить об ошибке"
BTN_MY_SIPS = "📞 SIP-номера"
BTN_MY_TICKETS = "📋 Мои заявки"
BTN_BALANCE = "💳 Баланс USDT"
BTN_TOPUP = "💰 Пополнение"
BTN_PROFILE = "Профиль"
BTN_MY_ID = "Мой ID"
BTN_HELP = "Справка"
BTN_GUIDES = "📖 Руководство"
BTN_RULES = "Правила"
BTN_ADMIN = "Поддержка"
BTN_MINI_APP = "📱 Личный кабинет"
BTN_ADMIN_HELP = "Команды персонала"

# —— Обратная совместимость ——
LEGACY_BTN_REPORT = "Новая заявка"
LEGACY_BTN_PROFILE = "👤 Профиль"
LEGACY_BTN_MY_ID = "🆔 Мой ID"
LEGACY_BTN_MY_SIPS = "📞 Мои SIP"
LEGACY_BTN_MY_TICKETS = "📋 Мои заявки"
LEGACY_BTN_BALANCE = "💳 Баланс"
LEGACY_BTN_TOPUP = "💰 Пополнить USDT"
LEGACY_BTN_HELP = "ℹ️ Помощь"
LEGACY_BTN_GUIDES = "📖 Руководства"
LEGACY_BTN_RULES = "📋 Правила"
LEGACY_BTN_ADMIN = "👨‍💼 Связь с админом"
LEGACY_BTN_MINI_APP = "📱 Личный кабинет"
LEGACY_BTN_ADMIN_HELP = "🔧 Админ-панель"
BTN_TEST_ERRORS = "🧪 Тест меню ошибок"

TEXTS_REPORT = frozenset({BTN_REPORT, LEGACY_BTN_REPORT})
TEXTS_PROFILE = frozenset({BTN_PROFILE, LEGACY_BTN_PROFILE})
TEXTS_MY_ID = frozenset({BTN_MY_ID, LEGACY_BTN_MY_ID})
TEXTS_MY_SIPS = frozenset({BTN_MY_SIPS, LEGACY_BTN_MY_SIPS})
TEXTS_MY_TICKETS = frozenset({BTN_MY_TICKETS, LEGACY_BTN_MY_TICKETS})
TEXTS_BALANCE = frozenset({BTN_BALANCE, LEGACY_BTN_BALANCE})
TEXTS_TOPUP = frozenset({BTN_TOPUP, LEGACY_BTN_TOPUP})
TEXTS_HELP = frozenset({BTN_HELP, LEGACY_BTN_HELP})
TEXTS_GUIDES = frozenset({BTN_GUIDES, LEGACY_BTN_GUIDES})
TEXTS_RULES = frozenset({BTN_RULES, LEGACY_BTN_RULES})
TEXTS_ADMIN = frozenset({BTN_ADMIN, LEGACY_BTN_ADMIN})
TEXTS_MINI_APP = frozenset({BTN_MINI_APP, LEGACY_BTN_MINI_APP})
TEXTS_ADMIN_HELP = frozenset({BTN_ADMIN_HELP, LEGACY_BTN_ADMIN_HELP})

PRIVATE_MENU_BUTTONS: frozenset[str] = frozenset({
    BTN_PROFILE,
    BTN_MY_ID,
    BTN_MY_SIPS,
    BTN_MY_TICKETS,
    BTN_REPORT,
    BTN_RULES,
    BTN_HELP,
    BTN_GUIDES,
    BTN_MINI_APP,
    BTN_BALANCE,
    BTN_TOPUP,
    BTN_ADMIN,
    BTN_ADMIN_HELP,
    BTN_TEST_ERRORS,
    LEGACY_BTN_REPORT,
    LEGACY_BTN_PROFILE,
    LEGACY_BTN_MY_ID,
    LEGACY_BTN_MY_SIPS,
    LEGACY_BTN_MY_TICKETS,
    LEGACY_BTN_BALANCE,
    LEGACY_BTN_TOPUP,
    LEGACY_BTN_HELP,
    LEGACY_BTN_GUIDES,
    LEGACY_BTN_RULES,
    LEGACY_BTN_ADMIN,
    LEGACY_BTN_MINI_APP,
    LEGACY_BTN_ADMIN_HELP,
    OTHER_ERROR_BUTTON,
    *(GROUP_ERROR_PRESETS[pid].button for pid in MAIN_PRESET_IDS),
})


def is_private_menu_button(text: str | None) -> bool:
    return bool(text and text.strip() in PRIVATE_MENU_BUTTONS)


def group_menu_button_hint(text: str) -> str | None:
    """Подсказка, если в группе нажали кнопку личного меню."""
    if text in TEXTS_PROFILE or text in TEXTS_MY_ID:
        return (
            "<b>Профиль и ID</b> доступны в личном чате с ботом.\n"
            "Откройте бота в ЛС и нажмите /start"
        )
    if text in TEXTS_MY_SIPS:
        return (
            f"SIP-номера — в личном чате: <b>{BTN_MY_SIPS}</b>\n"
            "В группе: <code>/sips</code> — номера владельца этой группы."
        )
    if text in TEXTS_MY_TICKETS:
        return (
            f"Заявки — в личном чате: <b>{BTN_MY_TICKETS}</b>\n"
            "В группе: <code>/status</code> — активные заявки группы."
        )
    if text in TEXTS_BALANCE or text in TEXTS_TOPUP:
        return (
            f"Баланс и пополнение USDT — в личном чате:\n"
            f"<b>{BTN_BALANCE}</b> · <b>{BTN_TOPUP}</b>"
        )
    if text in TEXTS_REPORT or text == OTHER_ERROR_BUTTON or text in {
        GROUP_ERROR_PRESETS[pid].button for pid in MAIN_PRESET_IDS
    }:
        return (
            "В группе заявки создаются так:\n"
            "1. <code>/err номер_sip</code>\n"
            "2. Выберите тип проблемы кнопкой\n\n"
            "Пример: <code>/err 100</code>"
        )
    if text in TEXTS_MINI_APP:
        return f"Личный кабинет — в ЛС: <b>{BTN_MINI_APP}</b>"
    if text in TEXTS_ADMIN:
        return f"Поддержка — в ЛС: <b>{BTN_ADMIN}</b> или /admin"
    if text in TEXTS_RULES:
        return f"Правила — в ЛС: /rules\nВ группе: /help"
    if text in TEXTS_HELP:
        return f"Справка — в ЛС: /help\nВ группе: /help"
    if text in TEXTS_GUIDES:
        return f"Руководства — в ЛС: <b>{BTN_GUIDES}</b> или /guides"
    if text in TEXTS_ADMIN_HELP:
        return "Команды персонала — в личном чате: /admin_help"
    if text == BTN_TEST_ERRORS:
        return "Тестовое меню ошибок — только в ЛС: /test_errors"
    return (
        "Это меню личного чата.\n"
        "В группе: <code>/err номер</code> · <code>/status</code> · /help"
    )
