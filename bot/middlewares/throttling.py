from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from redis.asyncio import Redis


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, redis: Redis, rate_limit: float = 0.5):
        self.redis = redis
        self.rate_limit = rate_limit  # секунды между запросами

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        user_id = event.from_user.id if event.from_user else None
        if user_id is None:
            return await handler(event, data)

        key = f"throttle:user:{user_id}"
        result = await self.redis.set(key, 1, px=int(self.rate_limit * 1000), nx=True)

        if result is None:
            # Уже есть ключ — слишком быстро
            await event.answer("⏳ Не так быстро, подождите немного.")
            return

        return await handler(event, data)
