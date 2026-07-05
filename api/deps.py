from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from db.base import async_session_maker
from db.models.user import User
from db.repositories.user_repo import UserRepository
from db.repositories.web_account_repo import WebAccountRepository

from api.auth import WEB_ACCOUNT_ID_KEY


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def get_redis() -> AsyncGenerator[Redis, None]:
    redis = Redis.from_url(settings.redis_url)
    try:
        yield redis
    finally:
        await redis.aclose()


async def get_web_actor(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    account_id = request.session.get(WEB_ACCOUNT_ID_KEY)
    user_repo = UserRepository(session)

    if account_id:
        account_repo = WebAccountRepository(session)
        account = await account_repo.get_by_id(int(account_id))
        if account and account.is_active:
            actor = await user_repo.get_by_id(account.actor_user_id)
            if actor:
                return actor

    actor = await user_repo.get_by_telegram_id(settings.superadmin_telegram_id)
    if not actor:
        raise HTTPException(
            status_code=503,
            detail="Superadmin user not found. Ask superadmin to send /start to the bot first.",
        )
    return actor
