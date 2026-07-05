"""Tests: XanaXGSM finance ledger Notion mapping."""
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import MagicMock

from services.notion.finance_ledger import (
    COL_CATEGORY,
    COL_OPERATION,
    COL_STATUS,
    COL_TYPE,
    ST_ACCOUNTED,
    TYPE_BUDGET,
    build_deposit_ledger_properties,
    deposit_comment_tag,
    expected_property_names,
)


def test_expected_columns_count():
    cols = expected_property_names()
    assert "Операция" in cols
    assert "Сумма USD" in cols
    assert len(cols) >= 10


def test_deposit_comment_tag():
    assert deposit_comment_tag(42) == "SIPCRM:#42"


def test_build_deposit_properties_confirmed():
    deposit = MagicMock()
    deposit.id = 7
    deposit.amount_usdt = Decimal("100.50")
    deposit.tx_hash = "abc123"
    deposit.confirmed_at = datetime(2024, 6, 29, tzinfo=timezone.utc)
    deposit.created_at = deposit.confirmed_at
    deposit.wallet = MagicMock(address="TAddr", network="TRC20")

    user = MagicMock()
    user.internal_id = "USR001"
    user.telegram_id = 12345
    user.first_name = "Test"

    props = build_deposit_ledger_properties(deposit, user, accounted=True)
    assert props[COL_OPERATION]["title"][0]["text"]["content"] == "Пополнение USDT #7"
    assert props[COL_STATUS]["select"]["name"] == ST_ACCOUNTED
    assert props[COL_TYPE]["select"]["name"] == TYPE_BUDGET
    assert props[COL_CATEGORY]["select"]["name"] == "Пополнение кассы"
    assert "SIPCRM:#7" in props["Комментарий"]["rich_text"][0]["text"]["content"]
