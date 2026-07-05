"""Проверка Telegram Web App initData."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import HTTPException

from bot.config import settings

MAX_AUTH_AGE_SECONDS = 86400


def validate_init_data(init_data: str) -> dict:
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing Telegram init data")

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="Invalid init data")

    data_check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret = hmac.new(b"WebAppData", settings.bot_token.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated, received_hash):
        raise HTTPException(status_code=401, detail="Invalid init data signature")

    auth_date = int(parsed.get("auth_date", "0") or "0")
    if auth_date and time.time() - auth_date > MAX_AUTH_AGE_SECONDS:
        raise HTTPException(status_code=401, detail="Init data expired")

    return parsed


def telegram_user_from_init(parsed: dict) -> dict:
    raw = parsed.get("user")
    if not raw:
        raise HTTPException(status_code=401, detail="User not found in init data")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=401, detail="Invalid user payload") from exc
