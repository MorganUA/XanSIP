import asyncio
import logging

from aiohttp import web
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
from bot.webhook.server import create_webhook_app

from bot.utils.bot_commands_setup import register_bot_commands

from bot.handlers import (
    start, profile, sip, tickets, my_tickets, error_catalog_test,
    rules, admin_contact, support_callbacks, finance, guides,
    group, admin_commands, group_tickets, group_help, fallback,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    from services.security import validate_production_config

    validate_production_config(settings)

    redis = Redis.from_url(settings.redis_url)
    storage = RedisStorage(redis=redis)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=storage)

    dp.update.middleware(DbSessionMiddleware())
    dp.update.middleware(AuthMiddleware())
    dp.update.middleware(BanMiddleware())
    dp.message.middleware(ThrottlingMiddleware(redis=redis, rate_limit=0.5))
    dp.callback_query.middleware(ThrottlingMiddleware(redis=redis, rate_limit=0.5))

    dp["redis"] = redis

    dp.include_router(group.router)
    dp.include_router(group_help.router)
    dp.include_router(admin_commands.router)
    dp.include_router(group_tickets.router)
    dp.include_router(support_callbacks.router)
    dp.include_router(start.router)
    dp.include_router(profile.router)
    dp.include_router(finance.router)
    dp.include_router(sip.router)
    dp.include_router(my_tickets.router)
    dp.include_router(tickets.router)
    dp.include_router(error_catalog_test.router)
    dp.include_router(rules.router)
    dp.include_router(admin_contact.router)
    dp.include_router(guides.router)
    dp.include_router(fallback.router)

    webhook_app = create_webhook_app(bot)
    runner = web.AppRunner(webhook_app)
    await runner.setup()
    site = web.TCPSite(runner, settings.bot_webhook_host, settings.bot_webhook_port)
    await site.start()
    logger.info(
        "Bot webhook server listening on %s:%s",
        settings.bot_webhook_host,
        settings.bot_webhook_port,
    )

    logger.info("SIP CRM bot starting...")
    await register_bot_commands(bot)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await bot.session.close()
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
