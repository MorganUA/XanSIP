import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from bot.config import settings
from bot.middlewares.db import DbSessionMiddleware
from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.ban import BanMiddleware
from bot.middlewares.throttling import ThrottlingMiddleware

from bot.handlers import (
    start, profile, sip, tickets,
    rules, admin_contact, support_callbacks,
    group, admin_commands, group_tickets,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    redis = Redis.from_url(settings.redis_url)
    storage = RedisStorage(redis=redis)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=storage)

    # Middleware
    dp.update.middleware(DbSessionMiddleware())
    dp.update.middleware(AuthMiddleware())
    dp.update.middleware(BanMiddleware())
    dp.message.middleware(ThrottlingMiddleware(redis=redis, rate_limit=0.5))

    dp["redis"] = redis

    # Роутеры — порядок важен
    dp.include_router(group.router)           # my_chat_member events
    dp.include_router(admin_commands.router)  # команды админа
    dp.include_router(group_tickets.router)   # /err в группах
    dp.include_router(start.router)
    dp.include_router(profile.router)
    dp.include_router(sip.router)
    dp.include_router(tickets.router)
    dp.include_router(rules.router)
    dp.include_router(admin_contact.router)
    dp.include_router(support_callbacks.router)

    logger.info("Бот запускается (MVP 2)...")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
