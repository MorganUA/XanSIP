"""Тесты Telegram Web App initData."""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from fastapi import HTTPException

from api.services.telegram_webapp import validate_init_data


def _make_init_data(bot_token: str, user: dict, auth_date: int = 1700000000) -> str:
    payload = {
        "auth_date": str(auth_date),
        "user": json.dumps(user, separators=(",", ":")),
    }
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(payload.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    payload["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return urlencode(payload)


def test_validate_init_data_ok(monkeypatch):
    token = "123456:ABC-DEF"
    monkeypatch.setattr("api.services.telegram_webapp.settings.bot_token", token)
    init = _make_init_data(token, {"id": 42, "first_name": "Test"}, auth_date=int(time.time()))
    parsed = validate_init_data(init)
    assert "user" in parsed


def test_validate_init_data_bad_hash():
    with pytest.raises(HTTPException) as exc:
        validate_init_data("auth_date=1&hash=bad")
    assert exc.value.status_code == 401
