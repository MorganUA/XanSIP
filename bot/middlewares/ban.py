from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, Message, CallbackQuery
from db.models.user import User


class BanMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("user")

        if not user or not user.is_banned:
            return await handler(event, data)

        reason = user.ban_reason or "Причина не указана"
        text = f"🚫 Ваш аккаунт заблокирован.\nПричина: {reason}"

        if isinstance(event, Update):
            if event.callback_query:
                await event.callback_query.answer(text, show_alert=True)
            elif event.message:
                await event.message.answer(text)
        elif isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        elif isinstance(event, Message):
            await event.answer(text)

        return None
