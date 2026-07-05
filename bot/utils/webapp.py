"""Telegram Web App URL helpers."""

from __future__ import annotations

import logging

from bot.config import settings

logger = logging.getLogger(__name__)


def is_https_webapp_url(url: str | None) -> bool:
    return bool(url and url.strip().lower().startswith("https://"))


def get_mini_app_url() -> str | None:
    """URL Mini App — только HTTPS (требование Telegram для WebApp / MenuButton)."""
    base = (settings.public_web_url or "").strip().rstrip("/")
    if not base:
        return None
    url = f"{base}/mini"
    if not is_https_webapp_url(url):
        logger.warning(
            "Mini App отключён: PUBLIC_WEB_URL=%s — Telegram принимает только HTTPS",
            base,
        )
        return None
    return url
