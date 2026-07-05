"""Shared helpers for QA scripts (no DB / HTTP dependencies)."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from urllib.parse import urlencode


def solve_captcha(question: str) -> str:
    m = re.match(r"(\d+)\s*\+\s*(\d+)", question or "")
    return str(int(m.group(1)) + int(m.group(2))) if m else "0"


def make_tma_init_data(bot_token: str, *, user_id: int = 424242, first_name: str = "QA") -> str:
    """Signed Telegram WebApp initData for live Mini App API checks."""
    payload = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": user_id, "first_name": first_name}, separators=(",", ":")),
    }
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(payload.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    payload["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return urlencode(payload)
