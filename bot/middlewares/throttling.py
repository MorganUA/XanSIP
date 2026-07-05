from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import TelegramObject, Message, CallbackQuery
from redis.asyncio import Redis


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, redis: Redis, rate_limit: float = 0.5):
        self.redis = redis
        self.rate_limit = rate_limit

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not self._should_throttle(event):
            return await handler(event, data)

        user_id = self._extract_user_id(event)
        if user_id is None:
            return await handler(event, data)

        key = f"throttle:user:{user_id}"
        allowed = await self.redis.set(
            key, 1, px=int(self.rate_limit * 1000), nx=True,
        )
        if allowed is None:
            await self._notify_too_fast(event)
            return None

        return await handler(event, data)

    @staticmethod
    def _should_throttle(event: TelegramObject) -> bool:
        """Антиспам только в личке — в группах не отвечаем на чужие сообщения."""
        if isinstance(event, Message):
            return event.chat.type == ChatType.PRIVATE
        if isinstance(event, CallbackQuery) and event.message:
            return event.message.chat.type == ChatType.PRIVATE
        return False

    @staticmethod
    def _extract_user_id(event: TelegramObject) -> int | None:
        if isinstance(event, CallbackQuery) and event.from_user:
            return event.from_user.id
        if isinstance(event, Message) and event.from_user:
            return event.from_user.id
        return None

    @staticmethod
    async def _notify_too_fast(event: TelegramObject) -> None:
        text = "⏳ Не так быстро, подождите немного."
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        elif isinstance(event, Message):
            await event.answer(text)
