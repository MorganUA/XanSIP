from aiogram import Router, F, Bot
from aiogram.types import ChatMemberUpdated, CallbackQuery, Message
from aiogram.filters import ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import User, UserRole
from db.repositories.group_repo import GroupRepository
from db.repositories.user_repo import UserRepository
from bot.utils.notify import notify_admin_new_group

router = Router()


# ─── Бот добавлен в группу ───────────────────────────────────────────

@router.my_chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def bot_added_to_group(
    event: ChatMemberUpdated,
    bot: Bot,
    session: AsyncSession,
    user: User,
):
    # Игнорируем личные чаты
    if event.chat.type not in ("group", "supergroup"):
        return

    group_repo = GroupRepository(session)
    existing = await group_repo.get_by_telegram_id(event.chat.id)

    if existing:
        if existing.is_approved:
            return  # Уже одобрена
        if existing.is_banned:
            await bot.leave_chat(event.chat.id)
            return

    # Создаём запись если нет
    if not existing:
        await group_repo.create(
            telegram_group_id=event.chat.id,
            group_name=event.chat.title,
            owner_user_id=user.id,
        )

    # Уведомляем суперадмина
    await notify_admin_new_group(
        bot=bot,
        group_telegram_id=event.chat.id,
        group_name=event.chat.title,
        added_by=user,
    )

    # Сообщаем в группу что ждём одобрения
    try:
        await bot.send_message(
            chat_id=event.chat.id,
            text=(
                "👋 Привет! Я бот поддержки SIP/GSM телефонии.\n\n"
                "⏳ Эта группа ожидает одобрения администратором.\n"
                "После одобрения я начну принимать заявки."
            ),
        )
    except Exception:
        pass


# ─── Бот удалён из группы ────────────────────────────────────────────

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
        await group_repo.reject(group)


# ─── Одобрение группы админом ────────────────────────────────────────

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

    await group_repo.approve(group, approved_by_id=user.id)

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>ОДОБРЕНО</b>",
        parse_mode="HTML",
    )

    try:
        await bot.send_message(
            chat_id=group_telegram_id,
            text=(
                "✅ Группа одобрена!\n\n"
                "Теперь участники могут сообщать об ошибках.\n"
                "Используйте команду /err или кнопку в меню."
            ),
        )
    except Exception as e:
        print(f"[approve_group] Не удалось написать в группу: {e}")

    await callback.answer("✅ Группа одобрена.")


# ─── Отклонение группы админом ───────────────────────────────────────

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

    await group_repo.reject(group)

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <b>ОТКЛОНЕНО</b>",
        parse_mode="HTML",
    )

    try:
        await bot.send_message(
            chat_id=group_telegram_id,
            text="❌ Группа не была одобрена администратором.",
        )
        await bot.leave_chat(group_telegram_id)
    except Exception:
        pass

    await callback.answer("❌ Группа отклонена.")
