import logging

from aiogram import Bot
from aiogram.exceptions import TelegramMigrateToChat
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def send_message_safe(
    bot: Bot,
    chat_id: int,
    text: str,
    *,
    parse_mode: str | None = "HTML",
    reply_markup=None,
    session: AsyncSession | None = None,
) -> tuple[int, int] | None:
    """Send a message; on supergroup migration retry and persist the new chat id."""
    from bot.services.notification_config import replace_chat_id

    try:
        msg = await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
        return msg.chat.id, msg.message_id
    except TelegramMigrateToChat as exc:
        new_id = exc.migrate_to_chat_id
        logger.warning("Chat %s migrated to supergroup %s", chat_id, new_id)
        if session is not None:
            await replace_chat_id(session, chat_id, new_id)
        msg = await bot.send_message(
            chat_id=new_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
        return msg.chat.id, msg.message_id
    except Exception:
        raise
