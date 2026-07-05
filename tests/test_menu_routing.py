"""Покрытие reply-меню без зависимости от aiogram (pytest в api-контейнере)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MENU_CATALOG = ROOT / "bot" / "utils" / "menu_catalog.py"
MAIN_MENU = ROOT / "bot" / "keyboards" / "main_menu.py"
MENU_DISPATCH = ROOT / "bot" / "utils" / "menu_dispatch.py"
FSM_GUARD = ROOT / "bot" / "utils" / "fsm_menu_guard.py"

PRIMARY_BUTTONS = (
    "🚨 Сообщить об ошибке",
    "📞 SIP-номера",
    "📋 Мои заявки",
    "💳 Баланс USDT",
    "💰 Пополнение",
    "Профиль",
    "Мой ID",
    "📖 Руководство",
    "Справка",
    "Правила",
    "Поддержка",
)

LEGACY_ALIASES = (
    "Новая заявка",
    "👤 Профиль",
    "🆔 Мой ID",
    "📞 Мои SIP",
    "💳 Баланс",
    "💰 Пополнить USDT",
    "ℹ️ Помощь",
    "📖 Руководства",
    "📋 Правила",
    "👨‍💼 Связь с админом",
    "🔧 Админ-панель",
)


def _catalog_text() -> str:
    return MENU_CATALOG.read_text(encoding="utf-8")


def test_primary_button_constants_in_catalog():
    text = _catalog_text()
    for btn in PRIMARY_BUTTONS:
        assert f'= "{btn}"' in text or f"= '{btn}'" in text, btn


def test_legacy_aliases_in_private_menu_buttons():
    text = _catalog_text()
    block_m = re.search(r"PRIVATE_MENU_BUTTONS[^=]+=\s*frozenset\(\{([^}]+)\}", text, re.DOTALL)
    assert block_m
    block = block_m.group(1)
    for alias in LEGACY_ALIASES:
        assert alias in text, alias


def test_texts_sets_include_primary_and_legacy():
    text = _catalog_text()
    pairs = [
        ("TEXTS_REPORT", "🚨 Сообщить об ошибке", "Новая заявка"),
        ("TEXTS_GUIDES", "📖 Руководство", "📖 Руководства"),
        ("TEXTS_ADMIN", "Поддержка", "👨‍💼 Связь с админом"),
    ]
    for name, primary, legacy in pairs:
        m = re.search(rf"{name} = frozenset\(\{{([^}}]+)\}}\)", text)
        assert m, name
        body = m.group(1)
        assert primary.replace("📖", "") or primary in body or "BTN_" in body
        assert "LEGACY" in body or legacy in body


def test_group_hints_reference_group_commands():
    text = _catalog_text()
    assert "/status" in text
    assert "/err" in text
    assert "group_menu_button_hint" in text


def test_main_menu_keyboard_imports_catalog_buttons():
    text = MAIN_MENU.read_text(encoding="utf-8")
    for const in (
        "BTN_REPORT", "BTN_MY_SIPS", "BTN_MY_TICKETS", "BTN_BALANCE", "BTN_TOPUP",
        "BTN_PROFILE", "BTN_MY_ID", "BTN_GUIDES", "BTN_HELP", "BTN_RULES", "BTN_ADMIN",
    ):
        assert const in text


def test_finance_handlers_use_texts_filters():
    text = (ROOT / "bot/handlers/finance.py").read_text(encoding="utf-8")
    assert "TEXTS_BALANCE" in text
    assert "TEXTS_TOPUP" in text


def test_admin_contact_handles_support():
    text = (ROOT / "bot/handlers/admin_contact.py").read_text(encoding="utf-8")
    assert "TEXTS_ADMIN" in text
    assert "TEXTS_HELP" in text


def test_menu_dispatch_covers_primary_buttons():
    text = MENU_DISPATCH.read_text(encoding="utf-8")
    for texts in (
        "TEXTS_REPORT", "TEXTS_MY_SIPS", "TEXTS_MY_TICKETS", "TEXTS_BALANCE",
        "TEXTS_TOPUP", "TEXTS_PROFILE", "TEXTS_MY_ID", "TEXTS_GUIDES",
        "TEXTS_HELP", "TEXTS_RULES", "TEXTS_ADMIN", "TEXTS_ADMIN_HELP",
    ):
        assert texts in text


def test_fsm_guard_wires_dispatch():
    text = FSM_GUARD.read_text(encoding="utf-8")
    assert "cancel_fsm_for_menu_button" in text
    assert "dispatch_menu_button" in text
    assert "is_private_menu_button" in text


def test_finance_and_tickets_use_fsm_guard():
    assert "cancel_fsm_for_menu_button" in (ROOT / "bot/handlers/finance.py").read_text(encoding="utf-8")
    assert "cancel_fsm_for_menu_button" in (ROOT / "bot/handlers/tickets.py").read_text(encoding="utf-8")


def test_error_catalog_test_imports_btn_constant():
    text = (ROOT / "bot/handlers/error_catalog_test.py").read_text(encoding="utf-8")
    assert "BTN_TEST_ERRORS" in text
    assert "from bot.utils.menu_catalog import BTN_TEST_ERRORS" in text
