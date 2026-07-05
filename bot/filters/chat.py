from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.types import Message


def apply_private_chat_filter(router: Router) -> Router:
    router.message.filter(F.chat.type == ChatType.PRIVATE)
    router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)
    return router
