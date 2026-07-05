from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.group_actions import PREFIX, get_group_help_keyboard
from bot.utils.group_commands import (
    resolve_group_context,
    send_group_sips,
    send_group_status,
)
from db.models.user import User, UserRole
from db.repositories.group_repo import GroupRepository
from db.repositories.user_repo import UserRepository

router = Router()

GROUP_HELP_TEXT = (
    "<b>SIP CRM · группа колл-центра</b>\n\n"
    "<b>Команды</b>\n"
    "• <code>/err номер_sip</code> — новая заявка (пример: <code>/err 100</code>)\n"
    "• <code>/status</code> — активные заявки группы\n"
    "• <code>/sips</code> — SIP-номера владельца\n"
    "• <code>/help</code> — справка\n\n"
    "<b>После /err</b> выберите тип проблемы кнопкой.\n\n"
    "Свободный текст не обрабатывается — только команды и кнопки.\n"
    "После решения заявки бот уведомит группу.\n\n"
    "Личное меню (профиль, финансы, SIP) — в ЛС с ботом: /start"
)


def _admin_group_hint(user: User) -> str:
    if user.role in (UserRole.admin, UserRole.superadmin):
        return "\n\nАдмин: /admin_help · одобрение групп — кнопки в уведомлении."
    return ""


async def _reply_help(message: Message, user: User) -> None:
    await message.reply(
        GROUP_HELP_TEXT + _admin_group_hint(user),
        parse_mode="HTML",
        reply_markup=get_group_help_keyboard(),
    )


@router.message(CommandStart(), F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
@router.message(Command("help"), F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def group_help(message: Message, user: User):
    await _reply_help(message, user)


@router.message(Command("status"), F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def group_status(message: Message, session: AsyncSession):
    group_repo = GroupRepository(session)
    group, err = await resolve_group_context(message, session, group_repo)
    if err:
        await message.reply(err)
        return
    await send_group_status(message, group, session)


@router.message(Command("sips"), F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def group_sips(message: Message, session: AsyncSession):
    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    group, err = await resolve_group_context(message, session, group_repo)
    if err:
        await message.reply(err)
        return
    await send_group_sips(message, group, session, user_repo)


@router.callback_query(F.data.startswith(f"{PREFIX}:"))
async def group_help_callback(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
):
    if callback.message.chat.type not in ("group", "supergroup"):
        await callback.answer("Только для групп.", show_alert=True)
        return

    action = callback.data.split(":")[1]
    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    group, err = await resolve_group_context(callback.message, session, group_repo)
    if err:
        await callback.answer(err, show_alert=True)
        return

    if action == "status":
        await send_group_status(callback.message, group, session)
        await callback.answer()
        return
    if action == "sips":
        await send_group_sips(callback.message, group, session, user_repo)
        await callback.answer()
        return
    if action == "help":
        await _reply_help(callback.message, user)
        await callback.answer()
        return
    await callback.answer()
