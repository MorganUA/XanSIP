"""Production security validation and HTTP helpers."""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot.config import Settings

WEAK_SECRET_VALUES = frozenset({
    "change-me",
    "change_me",
    "change-me-bot-secret",
    "ruuF123!",
    "SipAdm2026!",
    "SipSup2026!",
    "password",
    "secret",
    "your_password",
    "your_bot_token_here",
})

MIN_SECRET_KEY_LEN = 32
MIN_BOT_API_SECRET_LEN = 24
MIN_WEB_PASSWORD_LEN = 12


def is_production_env() -> bool:
    return os.environ.get("SIPCRM_ENV", "development").strip().lower() == "production"


def client_ip_from_request(request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def validate_production_config(settings: Settings) -> None:
    """Fail fast on weak secrets when SIPCRM_ENV=production."""
    if not is_production_env():
        return
    if os.environ.get("SKIP_SECRET_VALIDATION") == "1":
        return

    errors: list[str] = []

    if settings.secret_key in WEAK_SECRET_VALUES or len(settings.secret_key) < MIN_SECRET_KEY_LEN:
        errors.append(f"SECRET_KEY: min {MIN_SECRET_KEY_LEN} chars, not a placeholder")

    if settings.bot_api_secret in WEAK_SECRET_VALUES or len(settings.bot_api_secret) < MIN_BOT_API_SECRET_LEN:
        errors.append(f"BOT_API_SECRET: min {MIN_BOT_API_SECRET_LEN} chars, not a placeholder")

    if settings.web_admin_password in WEAK_SECRET_VALUES or len(settings.web_admin_password) < MIN_WEB_PASSWORD_LEN:
        errors.append(f"WEB_ADMIN_PASSWORD: min {MIN_WEB_PASSWORD_LEN} chars, not a placeholder")

    priv = os.environ.get("WEB_ADMIN_PRIV_PASSWORD", "")
    if priv in WEAK_SECRET_VALUES or len(priv) < MIN_WEB_PASSWORD_LEN:
        errors.append("WEB_ADMIN_PRIV_PASSWORD: required strong password in production")

    support = os.environ.get("WEB_ADMIN_SUPPORT_PASSWORD", "")
    if support in WEAK_SECRET_VALUES or len(support) < MIN_WEB_PASSWORD_LEN:
        errors.append("WEB_ADMIN_SUPPORT_PASSWORD: required strong password in production")

    redis_password = os.environ.get("REDIS_PASSWORD", "") or getattr(settings, "redis_password", "")
    if not redis_password or redis_password in WEAK_SECRET_VALUES:
        errors.append("REDIS_PASSWORD: required in production")

    if errors:
        msg = "Production security validation failed:\n  - " + "\n  - ".join(errors)
        print(msg, file=sys.stderr)
        raise SystemExit(1)


def build_redis_url(*, password: str = "", host: str = "redis", port: int = 6379, db: int = 0) -> str:
    if password:
        return f"redis://:{password}@{host}:{port}/{db}"
    return f"redis://{host}:{port}/{db}"
