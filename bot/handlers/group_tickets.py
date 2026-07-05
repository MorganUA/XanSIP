import logging

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.group_errors import get_group_preset
from bot.keyboards.group_err import get_main_error_keyboard, get_submenu_error_keyboard
from bot.services.crm_api import CrmApiError, create_group_ticket
from bot.utils.menu_catalog import (
    is_private_menu_button,
    group_menu_button_hint,
)
from bot.utils.formatting import escape_html
from bot.utils.group_err_session import GroupErrSession, clear_session, load_session, save_session
from bot.utils.group_access import group_access_error
from bot.utils.group_commands import resolve_group_context
from db.models.user import User
from db.repositories.group_repo import GroupRepository
from db.repositories.sip_repo import SipRepository
from db.repositories.user_repo import UserRepository

router = Router()
logger = logging.getLogger(__name__)


async def _resolve_sip_owner(group, user: User, session: AsyncSession) -> User:
    if not group.owner_user_id:
        return user
    user_repo = UserRepository(session)
    owner = await user_repo.get_by_id(group.owner_user_id)
    return owner or user


def _created_message(
    ticket_id: int,
    sip_number: str,
    error_label: str,
    *,
    support_notified: bool = True,
) -> str:
    base = (
        f"✅ <b>Заявка #{ticket_id} создана</b>\n"
        f"SIP <code>{escape_html(sip_number)}</code> — {escape_html(error_label)}.\n"
        "Ожидайте устранения."
    )
    if support_notified:
        return base + "\n\nПоддержка уведомлена. Статус: <code>/status</code>"
    return (
        base + "\n\n⚠️ Не удалось уведомить поддержку автоматически.\n"
        "Сообщите администратору номер заявки."
    )


@router.message(Command("err"), F.chat.type.in_({"group", "supergroup"}))
async def group_err_command(
    message: Message,
    user: User,
    session: AsyncSession,
    redis: Redis,
):
    group_repo = GroupRepository(session)
    group, err = await resolve_group_context(message, session, group_repo)
    if err:
        await message.reply(err)
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply(
            "⚠️ Формат: <code>/err номер_сип</code>\n"
            "Пример: <code>/err 100</code>\n\n"
            "После команды выберите тип ошибки из списка кнопок.",
            parse_mode="HTML",
        )
        return

    sip_number = args[1].strip()
    if not sip_number or len(sip_number) > 50:
        await message.reply("⚠️ Некорректный SIP-номер.")
        return

    sip_owner = await _resolve_sip_owner(group, user, session)
    sip_repo = SipRepository(session)
    sip = await sip_repo.get_by_number_and_user(sip_number, sip_owner.id)
    if not sip:
        await message.reply(
            f"⛔ SIP <code>{escape_html(sip_number)}</code> не найден "
            f"у владельца группы (<code>{escape_html(sip_owner.internal_id)}</code>).",
            parse_mode="HTML",
        )
        return

    await save_session(
        redis,
        message.chat.id,
        user.id,
        GroupErrSession(
            sip_number=sip_number,
            group_db_id=group.id,
            sip_id=sip.id,
            owner_user_id=sip_owner.id,
        ),
    )

    await message.reply(
        f"📞 SIP: <code>{escape_html(sip_number)}</code>\n"
        "Выберите тип ошибки:",
        parse_mode="HTML",
        reply_markup=get_main_error_keyboard(),
    )


@router.callback_query(F.data.startswith("gerre:"))
async def group_err_callback(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    redis: Redis,
    bot: Bot,
):
    if callback.message.chat.type not in ("group", "supergroup"):
        await callback.answer("⛔ Только для групп.", show_alert=True)
        return

    parts = callback.data.split(":")
    action = parts[1]

    if action == "more":
        await callback.message.edit_reply_markup(reply_markup=get_submenu_error_keyboard())
        await callback.answer()
        return

    if action == "back":
        await callback.message.edit_reply_markup(reply_markup=get_main_error_keyboard())
        await callback.answer()
        return

    if action == "cancel":
        await clear_session(redis, callback.message.chat.id, user.id)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Отменено")
        return

    if action not in ("m", "s"):
        await callback.answer()
        return

    preset_id = parts[2]
    preset = get_group_preset(preset_id)
    if not preset:
        await callback.answer("⚠️ Неизвестный тип ошибки.", show_alert=True)
        return

    err_session = await load_session(redis, callback.message.chat.id, user.id)
    if not err_session:
        await callback.answer(
            "⏱ Сессия истекла. Повторите: /err номер_сип",
            show_alert=True,
        )
        return

    group_repo = GroupRepository(session)
    group = await group_repo.get_by_telegram_id(callback.message.chat.id)
    blocked = group_access_error(group)
    if blocked:
        await callback.answer(blocked[:200], show_alert=True)
        return

    await callback.answer("⏳ Создаём заявку…")

    try:
        result = await create_group_ticket(
            sip_number=err_session.sip_number,
            error_preset_id=preset_id,
            initiator_telegram_id=user.telegram_id,
            group_chat_id=callback.message.chat.id,
        )
    except CrmApiError as exc:
        await callback.message.reply(f"❌ {escape_html(str(exc))}", parse_mode="HTML")
        return

    await clear_session(redis, callback.message.chat.id, user.id)

    from db.repositories.ticket_repo import TicketRepository
    from db.repositories.sip_repo import SipRepository
    from db.repositories.user_repo import UserRepository
    from bot.utils.notify import notify_support_new_ticket

    ticket_repo = TicketRepository(session)
    sip_repo = SipRepository(session)
    user_repo = UserRepository(session)
    group_repo = GroupRepository(session)

    ticket = await ticket_repo.get_by_id(result["ticket_id"])
    sip = await sip_repo.get_by_id(err_session.sip_id)
    sip_owner = await user_repo.get_by_id(err_session.owner_user_id)
    group = await group_repo.get_by_id(err_session.group_db_id)

    support_notified = False
    if ticket and sip and sip_owner and group:
        preset = get_group_preset(preset_id)
        msg_id = await notify_support_new_ticket(
            bot, ticket, sip_owner, sip, group,
            error_label=preset.label if preset else result.get("error_label"),
            session=session,
        )
        support_notified = msg_id is not None
        if msg_id:
            await ticket_repo.set_support_message_id(ticket, msg_id)

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(
        _created_message(
            result["ticket_id"],
            result["sip_number"],
            result.get("error_label", preset.label),
            support_notified=support_notified,
        ),
        parse_mode="HTML",
    )


@router.message(F.text, F.chat.type.in_({"group", "supergroup"}))
async def group_unknown_text(message: Message):
    """Подсказка при нажатии кнопок личного меню; прочий текст — без ответа."""
    if not message.text:
        return
    if message.text.startswith("/"):
        cmd = message.text.split()[0].split("@")[0].lower()
        known = {
            "/start", "/help", "/err", "/status", "/sips",
            "/ban_user", "/unban_user", "/ban_group", "/unban_group",
            "/set_group_owner", "/set_role", "/add_sip", "/remove_sip",
            "/enable_sip", "/admin_help", "/list_groups",
        }
        if cmd not in known:
            await message.reply(
                "ℹ️ Неизвестная команда.\n"
                "Доступно: <code>/err</code> · <code>/status</code> · "
                "<code>/sips</code> · <code>/help</code>",
                parse_mode="HTML",
            )
        return
    if is_private_menu_button(message.text):
        await message.reply(
            group_menu_button_hint(message.text),
            parse_mode="HTML",
        )
