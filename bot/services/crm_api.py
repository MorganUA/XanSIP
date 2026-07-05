import logging

import aiohttp

from bot.config import settings

logger = logging.getLogger(__name__)


class CrmApiError(Exception):
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


async def create_group_ticket(
    *,
    sip_number: str,
    error_preset_id: str,
    initiator_telegram_id: int,
    group_chat_id: int,
) -> dict:
    url = f"{settings.crm_api_url.rstrip('/')}/api/tickets/create"
    payload = {
        "sip_number": sip_number,
        "error_preset_id": error_preset_id,
        "initiator_telegram_id": initiator_telegram_id,
        "group_chat_id": group_chat_id,
    }
    headers = {
        "Content-Type": "application/json",
        "X-Bot-Secret": settings.bot_api_secret,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    detail = data.get("detail") if isinstance(data, dict) else str(data)
                    raise CrmApiError(detail or f"HTTP {resp.status}", resp.status)
                return data
    except CrmApiError:
        raise
    except Exception as exc:
        logger.exception("CRM API create ticket failed")
        raise CrmApiError(str(exc)) from exc
