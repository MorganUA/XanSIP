"""Unit tests: USDT amount parsing."""
import pytest

from db.repositories.finance_repo import parse_usdt_amount


def test_parse_usdt_amount_basic():
    assert parse_usdt_amount("100") == parse_usdt_amount("100.0")
    assert parse_usdt_amount("10,5") == parse_usdt_amount("10.5")
    assert parse_usdt_amount("  25.123456  ") == parse_usdt_amount("25.123456")


def test_parse_usdt_amount_rejects_invalid():
    with pytest.raises(ValueError, match="больше 0"):
        parse_usdt_amount("0")
    with pytest.raises(ValueError, match="больше 0"):
        parse_usdt_amount("-5")
    with pytest.raises(ValueError, match="Некорректная"):
        parse_usdt_amount("abc")
