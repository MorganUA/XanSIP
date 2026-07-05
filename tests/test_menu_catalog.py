from bot.utils.menu_catalog import (
    BTN_ADMIN,
    BTN_BALANCE,
    BTN_MY_SIPS,
    BTN_MY_TICKETS,
    BTN_PROFILE,
    BTN_REPORT,
    BTN_TOPUP,
    LEGACY_BTN_REPORT,
    TEXTS_REPORT,
    is_private_menu_button,
    group_menu_button_hint,
)


def test_private_menu_buttons_recognized():
    assert is_private_menu_button(BTN_MY_TICKETS)
    assert is_private_menu_button(BTN_REPORT)
    assert is_private_menu_button(LEGACY_BTN_REPORT)
    assert is_private_menu_button("🚫 Фрод")
    assert not is_private_menu_button("привет")


def test_legacy_report_in_texts_report():
    assert LEGACY_BTN_REPORT in TEXTS_REPORT
    assert BTN_REPORT in TEXTS_REPORT
    assert BTN_REPORT.startswith("🚨")


def test_group_hint_for_my_tickets():
    hint = group_menu_button_hint(BTN_MY_TICKETS)
    assert "/status" in hint


def test_main_buttons_have_emoji_on_primary():
    assert BTN_REPORT.startswith("🚨")
    assert BTN_MY_SIPS.startswith("📞")
    assert BTN_MY_TICKETS.startswith("📋")
    assert BTN_BALANCE.startswith("💳")
    assert BTN_TOPUP.startswith("💰")
    assert not BTN_PROFILE.startswith(("🚨", "📞", "📋", "💳", "💰"))


def test_menu_button_length_telegram_limit():
    from bot.utils.menu_catalog import (
        BTN_HELP,
        BTN_MINI_APP,
        BTN_MY_ID,
        BTN_RULES,
    )
    for label in (
        BTN_REPORT, BTN_MY_SIPS, BTN_MY_TICKETS, BTN_BALANCE, BTN_TOPUP,
        BTN_PROFILE, BTN_MY_ID, BTN_HELP, BTN_RULES, BTN_ADMIN, BTN_MINI_APP,
    ):
        assert len(label) <= 64, label
