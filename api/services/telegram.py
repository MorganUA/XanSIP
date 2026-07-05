import logging

import httpx

from bot.config import settings

logger = logging.getLogger(__name__)


async def send_message(chat_id: int, text: str, *, parse_mode: str | None = "HTML") -> bool:
    url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
    payload: dict = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return True
    except Exception:
        logger.exception("Failed to send Telegram message to %s", chat_id)
        return False


async def leave_chat(chat_id: int) -> bool:
    url = f"https://api.telegram.org/bot{settings.bot_token}/leaveChat"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, json={"chat_id": chat_id})
            response.raise_for_status()
            return True
    except Exception:
        logger.exception("Failed to leave chat %s", chat_id)
        return False
