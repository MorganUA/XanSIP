from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from db.models.user import User


class BanMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("user")

        if user and user.is_banned:
            reason = user.ban_reason or "Причина не указана"
            text = f"🚫 Ваш аккаунт заблокирован.\nПричина: {reason}"

            if isinstance(event, Message):
                await event.answer(text)
            elif isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            return  # Останавливаем обработку

        return await handler(event, data)
