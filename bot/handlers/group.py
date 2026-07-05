import logging

from aiogram import Router, F, Bot
from aiogram.types import ChatMemberUpdated, CallbackQuery
from aiogram.filters import ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import User, UserRole
from db.repositories.group_repo import GroupRepository
from bot.utils.notify import notify_admin_new_group

router = Router()
logger = logging.getLogger(__name__)


@router.my_chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def bot_added_to_group(
    event: ChatMemberUpdated,
    bot: Bot,
    session: AsyncSession,
    user: User,
):
    if event.chat.type not in ("group", "supergroup"):
        return

    group_repo = GroupRepository(session)
    existing = await group_repo.get_by_telegram_id(event.chat.id)
    if not existing:
        deleted = await group_repo.get_by_telegram_id_any(event.chat.id)
        if deleted and deleted.is_deleted:
            existing = await group_repo.restore_deleted(
                deleted,
                group_name=event.chat.title,
                owner_user_id=user.id,
            )

    if existing:
        if existing.is_approved:
            return
        if existing.is_banned:
            await bot.leave_chat(event.chat.id)
            return
    else:
        await group_repo.create(
            telegram_group_id=event.chat.id,
            group_name=event.chat.title,
            owner_user_id=user.id,
        )

    await notify_admin_new_group(
        bot=bot,
        group_telegram_id=event.chat.id,
        group_name=event.chat.title,
        added_by=user,
        session=session,
    )

    try:
        await bot.send_message(
            chat_id=event.chat.id,
            text=(
                "👋 Привет! Я бот поддержки SIP/GSM телефонии.\n\n"
                "⏳ Эта группа ожидает одобрения администратором.\n"
                "После одобрения: <code>/err номер_сип</code> → кнопки ошибок.\n"
                "Справка: /help"
            ),
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("Failed to greet group %s", event.chat.id)


@router.my_chat_member(ChatMemberUpdatedFilter(IS_MEMBER >> IS_NOT_MEMBER))
async def bot_removed_from_group(
    event: ChatMemberUpdated,
    session: AsyncSession,
):
    if event.chat.type not in ("group", "supergroup"):
        return

    group_repo = GroupRepository(session)
    group = await group_repo.get_by_telegram_id(event.chat.id)
    if group:
        await group_repo.mark_bot_left(group)


@router.callback_query(F.data.startswith("group:approve:"))
async def approve_group(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    bot: Bot,
):
    if user.role not in (UserRole.admin, UserRole.superadmin):
        await callback.answer("⛔ Нет прав.", show_alert=True)
        return

    group_telegram_id = int(callback.data.split(":")[2])
    group_repo = GroupRepository(session)
    group = await group_repo.get_by_telegram_id(group_telegram_id)

    if not group:
        await callback.answer("⚠️ Группа не найдена.", show_alert=True)
        return

    if group.is_approved:
        await callback.answer("ℹ️ Группа уже одобрена.", show_alert=True)
        return

    await group_repo.approve(group, approved_by_id=user.id)

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>ОДОБРЕНО</b>",
        parse_mode="HTML",
        reply_markup=None,
    )

    try:
        await bot.send_message(
            chat_id=group_telegram_id,
            text=(
                "✅ Группа одобрена!\n\n"
                "Сообщайте об ошибках командой:\n"
                "<code>/err номер_сип</code>\n"
                "Пример: <code>/err 100</code>\n"
                "Затем выберите тип ошибки из кнопок.",
            ),
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("Failed to notify approved group %s", group_telegram_id)

    await callback.answer("✅ Группа одобрена.")


@router.callback_query(F.data.startswith("group:reject:"))
async def reject_group(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    bot: Bot,
):
    if user.role not in (UserRole.admin, UserRole.superadmin):
        await callback.answer("⛔ Нет прав.", show_alert=True)
        return

    group_telegram_id = int(callback.data.split(":")[2])
    group_repo = GroupRepository(session)
    group = await group_repo.get_by_telegram_id(group_telegram_id)

    if not group:
        await callback.answer("⚠️ Группа не найдена.", show_alert=True)
        return

    if group.is_banned:
        await callback.answer("ℹ️ Группа уже отклонена.", show_alert=True)
        return

    await group_repo.reject(group)

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <b>ОТКЛОНЕНО</b>",
        parse_mode="HTML",
        reply_markup=None,
    )

    try:
        await bot.send_message(
            chat_id=group_telegram_id,
            text="❌ Группа не была одобрена администратором.",
        )
        await bot.leave_chat(group_telegram_id)
    except Exception:
        logger.exception("Failed to leave rejected group %s", group_telegram_id)

    await callback.answer("❌ Группа отклонена.")
