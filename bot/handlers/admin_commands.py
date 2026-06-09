from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import User, UserRole
from db.models.sip_account import SipAccount
from db.repositories.user_repo import UserRepository
from db.repositories.group_repo import GroupRepository

router = Router()


def _is_admin(user: User) -> bool:
    return user.role in (UserRole.admin, UserRole.superadmin)


@router.message(Command("ban_user"))
async def ban_user(message: Message, user: User, session: AsyncSession):
    if not _is_admin(user):
        await message.answer("⛔ Нет прав.")
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("Использование: /ban_user telegram_id причина")
        return
    try:
        target_telegram_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный Telegram ID.")
        return
    reason = args[2]
    repo = UserRepository(session)
    target = await repo.get_by_telegram_id(target_telegram_id)
    if not target:
        await message.answer("⚠️ Пользователь не найден.")
        return
    if target.telegram_id == user.telegram_id:
        await message.answer("⛔ Нельзя заблокировать себя.")
        return
    if target.role in (UserRole.admin, UserRole.superadmin):
        await message.answer("⛔ Нельзя заблокировать администратора.")
        return
    await repo.ban(target, reason, banned_by_id=user.id)
    await message.answer(f"✅ Пользователь {target_telegram_id} заблокирован. Причина: {reason}")


@router.message(Command("unban_user"))
async def unban_user(message: Message, user: User, session: AsyncSession):
    if not _is_admin(user):
        await message.answer("⛔ Нет прав.")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /unban_user telegram_id")
        return
    try:
        target_telegram_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный Telegram ID.")
        return
    repo = UserRepository(session)
    target = await repo.get_by_telegram_id(target_telegram_id)
    if not target:
        await message.answer("⚠️ Пользователь не найден.")
        return
    await repo.unban(target)
    await message.answer(f"✅ Пользователь {target_telegram_id} разблокирован.")


@router.message(Command("ban_group"))
async def ban_group(message: Message, user: User, session: AsyncSession):
    if not _is_admin(user):
        await message.answer("⛔ Нет прав.")
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("Использование: /ban_group group_id причина")
        return
    try:
        group_telegram_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный ID группы.")
        return
    reason = args[2]
    repo = GroupRepository(session)
    group = await repo.get_by_telegram_id(group_telegram_id)
    if not group:
        await message.answer("⚠️ Группа не найдена.")
        return
    await repo.ban(group, reason)
    await message.answer(f"✅ Группа {group_telegram_id} заблокирована. Причина: {reason}")


@router.message(Command("set_role"))
async def set_role(message: Message, user: User, session: AsyncSession):
    if user.role != UserRole.superadmin:
        await message.answer("⛔ Только для суперадмина.")
        return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Использование: /set_role telegram_id role\nРоли: user, support, admin, superadmin")
        return
    try:
        target_telegram_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный Telegram ID.")
        return
    role_str = args[2].lower()
    try:
        new_role = UserRole(role_str)
    except ValueError:
        await message.answer("⚠️ Неверная роль. Доступно: user, support, admin, superadmin")
        return
    repo = UserRepository(session)
    target = await repo.get_by_telegram_id(target_telegram_id)
    if not target:
        await message.answer("⚠️ Пользователь не найден.")
        return
    if target.telegram_id == user.telegram_id:
        await message.answer("⛔ Нельзя менять роль самому себе.")
        return
    target.role = new_role
    await session.commit()
    await message.answer(f"✅ Роль пользователя {target_telegram_id} изменена на {new_role.value}.")


@router.message(Command("add_sip"))
async def add_sip(message: Message, user: User, session: AsyncSession):
    if not _is_admin(user):
        await message.answer("⛔ Нет прав.")
        return
    args = message.text.split(maxsplit=3)
    if len(args) < 3:
        await message.answer("Использование: /add_sip telegram_id sip_number [описание]")
        return
    try:
        target_telegram_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный Telegram ID.")
        return
    sip_number = args[2]
    description = args[3] if len(args) > 3 else None
    user_repo = UserRepository(session)
    target = await user_repo.get_by_telegram_id(target_telegram_id)
    if not target:
        await message.answer("⚠️ Пользователь не найден.")
        return
    sip = SipAccount(user_id=target.id, sip_number=sip_number, description=description, added_by=user.id)
    session.add(sip)
    await session.commit()
    await message.answer(f"✅ SIP {sip_number} добавлен пользователю {target_telegram_id}.")
