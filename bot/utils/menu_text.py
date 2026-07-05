"""Тексты меню и ссылки на Web CRM."""

from bot.config import settings


def web_crm_url_line() -> str:
    url = (settings.public_web_url or "").strip().rstrip("/")
    if not url or url.startswith("http://"):
        return ""
    return f"Web CRM: {url}"
