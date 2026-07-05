from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from sqlalchemy.ext.asyncio import AsyncSession
from db.repositories.user_repo import UserRepository
from db.models.user import UserRole
from bot.utils.internal_id import generate_unique_internal_id
from bot.config import settings


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session: AsyncSession = data.get("session")
        if session is None:
            return await handler(event, data)

        tg_user = data.get("event_from_user")

        if tg_user is None or tg_user.is_bot:
            return await handler(event, data)

        repo = UserRepository(session)
        user = await repo.get_by_telegram_id(tg_user.id)

        if user is None:
            role = (
                UserRole.superadmin
                if tg_user.id == settings.superadmin_telegram_id
                else UserRole.user
            )
            internal_id = await generate_unique_internal_id(session)
            user = await repo.create(
                telegram_id=tg_user.id,
                internal_id=internal_id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
                role=role,
            )
        else:
            await repo.sync_profile(
                user,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
            )

        data["user"] = user
        return await handler(event, data)
