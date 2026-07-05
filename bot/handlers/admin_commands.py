from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters.chat import apply_private_chat_filter
from bot.keyboards.main_menu import get_main_menu
from bot.utils.admin_audit import log_admin_action
from bot.services.sip_work_stats import build_sip_work_report, format_stats_telegram
from bot.utils.menu_catalog import BTN_ADMIN_HELP, BTN_TEST_ERRORS, TEXTS_ADMIN_HELP
from db.models.sip_account import SipStatus
from db.models.user import User, UserRole
from db.repositories.group_repo import GroupRepository
from db.repositories.sip_repo import SipRepository
from db.repositories.user_repo import UserRepository

router = apply_private_chat_filter(Router())


def _is_admin(user: User) -> bool:
    return user.role in (UserRole.admin, UserRole.superadmin)


def _admin_help_text() -> str:
    return "\n".join([
        f"<b>{BTN_ADMIN_HELP}</b>\n",
        "<b>Пользователи</b>",
        "/ban_user id причина",
        "/unban_user id",
        "/set_role id role — только superadmin\n",
        "<b>SIP</b>",
        "/add_sip id номер [описание] — добавить или реактивировать отключённый",
        "/remove_sip id номер — отключить",
        "/enable_sip id номер — активировать отключённый\n",
        "<b>Группы</b>",
        "/ban_group group_id причина",
        "/unban_group group_id",
        "/set_group_owner group_id telegram_id",
        "/list_groups",
        "",
        "<b>Web CRM:</b> панель управления (Service Desk, SIP, группы, уведомления, статистика)",
        "/stats [дней] — краткий отчёт о работе SIP (по умолчанию 30)",
    ])


@router.message(F.text.in_(TEXTS_ADMIN_HELP))
@router.message(Command("admin_help"))
async def admin_help(message: Message, user: User):
    if user.role == UserRole.support:
        await message.answer(
            "🛠 <b>Поддержка</b>\n\n"
            "• Новые заявки приходят в чат поддержки с кнопками действий\n"
            "• Взять в работу · Решено · Отклонить · Ожидание инфо\n"
            "• Web CRM: очередь колл-центра, статистика SIP (/stats)\n\n"
            "Полные админ-команды — только у admin/superadmin.",
            parse_mode="HTML",
            reply_markup=get_main_menu(user),
        )
        return
    if not _is_admin(user):
        await message.answer("⛔ Нет прав.", reply_markup=get_main_menu(user))
        return
    await message.answer(_admin_help_text(), parse_mode="HTML", reply_markup=get_main_menu(user))


def _is_staff(user: User) -> bool:
    return user.role in (UserRole.support, UserRole.admin, UserRole.superadmin)


@router.message(Command("stats"))
async def cmd_stats(message: Message, user: User, session: AsyncSession):
    if not _is_staff(user):
        await message.answer("⛔ Нет прав.", reply_markup=get_main_menu(user))
        return
    days = 30
    parts = (message.text or "").split()
    if len(parts) > 1:
        try:
            days = int(parts[1])
        except ValueError:
            await message.answer(
                "Использование: /stats [дней]\nПример: /stats 7",
                reply_markup=get_main_menu(user),
            )
            return
    report = await build_sip_work_report(session, days=days)
    await message.answer(
        format_stats_telegram(report),
        parse_mode="HTML",
        reply_markup=get_main_menu(user),
    )


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
    await log_admin_action(
        session, user, "ban_user",
        entity_type="user", entity_id=target.id,
        new_value={"telegram_id": target_telegram_id, "reason": reason},
    )
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
    await log_admin_action(
        session, user, "unban_user",
        entity_type="user", entity_id=target.id,
        new_value={"telegram_id": target_telegram_id},
    )
    await message.answer(f"✅ Пользователь {target_telegram_id} разблокирован.")


@router.message(Command("ban_group"))
async def ban_group(message: Message, user: User, session: AsyncSession, bot: Bot):
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
    await log_admin_action(
        session, user, "ban_group",
        entity_type="group", entity_id=group.id,
        new_value={"telegram_group_id": group_telegram_id, "reason": reason},
    )
    try:
        await bot.send_message(group_telegram_id, f"🚫 Группа заблокирована. Причина: {reason}")
        await bot.leave_chat(group_telegram_id)
    except Exception:
        pass
    await message.answer(f"✅ Группа {group_telegram_id} заблокирована. Причина: {reason}")


@router.message(Command("unban_group"))
async def unban_group(message: Message, user: User, session: AsyncSession):
    if not _is_admin(user):
        await message.answer("⛔ Нет прав.")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /unban_group group_id")
        return
    try:
        group_telegram_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный ID группы.")
        return
    repo = GroupRepository(session)
    group = await repo.get_by_telegram_id(group_telegram_id)
    if not group:
        await message.answer("⚠️ Группа не найдена.")
        return
    await repo.unban(group)
    await log_admin_action(
        session, user, "unban_group",
        entity_type="group", entity_id=group.id,
        new_value={"telegram_group_id": group_telegram_id},
    )
    await message.answer(f"✅ Группа {group_telegram_id} разблокирована.")


@router.message(Command("set_group_owner"))
async def set_group_owner(message: Message, user: User, session: AsyncSession):
    if not _is_admin(user):
        await message.answer("⛔ Нет прав.")
        return
    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "Использование: /set_group_owner group_id telegram_id\n"
            "Пример: /set_group_owner -1001234567890 7125671123"
        )
        return
    try:
        group_telegram_id = int(args[1])
        owner_telegram_id = int(args[2])
    except ValueError:
        await message.answer("⚠️ Неверные ID.")
        return

    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    group = await group_repo.get_by_telegram_id(group_telegram_id)
    if not group:
        await message.answer("⚠️ Группа не найдена.")
        return
    owner = await user_repo.get_by_telegram_id(owner_telegram_id)
    if not owner:
        await message.answer("⚠️ Пользователь не найден. Пусть сначала напишет боту /start.")
        return

    old_owner = group.owner_user_id
    await group_repo.set_owner(group, owner.id)
    await log_admin_action(
        session, user, "set_group_owner",
        entity_type="group", entity_id=group.id,
        old_value={"owner_user_id": old_owner},
        new_value={"owner_user_id": owner.id, "owner_telegram_id": owner_telegram_id},
    )
    await message.answer(
        f"✅ Владелец группы {group_telegram_id} — "
        f"{owner.internal_id} (telegram_id: {owner_telegram_id})."
    )


@router.message(Command("set_role"))
async def set_role(message: Message, user: User, session: AsyncSession):
    if user.role != UserRole.superadmin:
        await message.answer("⛔ Только для суперадмина.")
        return
    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "Использование: /set_role telegram_id role\n"
            "Роли: user, support, admin, superadmin"
        )
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
    old_role = target.role.value
    target.role = new_role
    await session.commit()
    await log_admin_action(
        session, user, "set_role",
        entity_type="user", entity_id=target.id,
        old_value={"role": old_role},
        new_value={"role": new_role.value},
    )
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
    sip_number = args[2].strip()
    description = args[3] if len(args) > 3 else None
    if not sip_number or len(sip_number) > 50:
        await message.answer("⚠️ Некорректный SIP-номер.")
        return

    user_repo = UserRepository(session)
    sip_repo = SipRepository(session)
    target = await user_repo.get_by_telegram_id(target_telegram_id)
    if not target:
        await message.answer("⚠️ Пользователь не найден.")
        return

    existing = await sip_repo.get_by_number_and_user(sip_number, target.id)
    if existing:
        if existing.status == SipStatus.disabled:
            await sip_repo.update_status(existing, SipStatus.active)
            if description:
                existing.description = description
                await session.commit()
            await log_admin_action(
                session, user, "enable_sip",
                entity_type="sip", entity_id=existing.id,
                old_value={"status": SipStatus.disabled.value},
                new_value={"status": SipStatus.active.value},
            )
            await message.answer(
                f"✅ SIP {sip_number} повторно активирован у пользователя {target_telegram_id}."
            )
            return
        await message.answer(f"⚠️ SIP {sip_number} уже есть у этого пользователя.")
        return

    sip = await sip_repo.create(
        user_id=target.id,
        sip_number=sip_number,
        description=description,
        added_by=user.id,
    )
    await log_admin_action(
        session, user, "add_sip",
        entity_type="sip", entity_id=sip.id,
        new_value={"sip_number": sip_number, "user_id": target.id},
    )
    await message.answer(f"✅ SIP {sip_number} добавлен пользователю {target_telegram_id}.")


@router.message(Command("remove_sip"))
async def remove_sip(message: Message, user: User, session: AsyncSession):
    if not _is_admin(user):
        await message.answer("⛔ Нет прав.")
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("Использование: /remove_sip telegram_id sip_number")
        return
    try:
        target_telegram_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный Telegram ID.")
        return
    sip_number = args[2]
    user_repo = UserRepository(session)
    sip_repo = SipRepository(session)
    target = await user_repo.get_by_telegram_id(target_telegram_id)
    if not target:
        await message.answer("⚠️ Пользователь не найден.")
        return
    sip = await sip_repo.get_by_number_and_user(sip_number, target.id)
    if not sip:
        await message.answer("⚠️ SIP не найден.")
        return
    await sip_repo.update_status(sip, SipStatus.disabled)
    await log_admin_action(
        session, user, "remove_sip",
        entity_type="sip", entity_id=sip.id,
        new_value={"status": SipStatus.disabled.value},
    )
    await message.answer(f"✅ SIP {sip_number} отключён у пользователя {target_telegram_id}.")


@router.message(Command("enable_sip"))
async def enable_sip(message: Message, user: User, session: AsyncSession):
    if not _is_admin(user):
        await message.answer("⛔ Нет прав.")
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("Использование: /enable_sip telegram_id sip_number")
        return
    try:
        target_telegram_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный Telegram ID.")
        return
    sip_number = args[2].strip()
    user_repo = UserRepository(session)
    sip_repo = SipRepository(session)
    target = await user_repo.get_by_telegram_id(target_telegram_id)
    if not target:
        await message.answer("⚠️ Пользователь не найден.")
        return
    sip = await sip_repo.get_by_number_and_user(sip_number, target.id)
    if not sip:
        await message.answer("⚠️ SIP не найден.")
        return
    if sip.status == SipStatus.active:
        await message.answer(f"ℹ️ SIP {sip_number} уже активен.")
        return
    if sip.status != SipStatus.disabled:
        await message.answer(
            f"⚠️ SIP {sip_number} в статусе «{sip.status.value}» — "
            "повторная активация только для отключённых."
        )
        return
    await sip_repo.update_status(sip, SipStatus.active)
    await log_admin_action(
        session, user, "enable_sip",
        entity_type="sip", entity_id=sip.id,
        old_value={"status": SipStatus.disabled.value},
        new_value={"status": SipStatus.active.value},
    )
    await message.answer(f"✅ SIP {sip_number} активирован у пользователя {target_telegram_id}.")


@router.message(Command("list_groups"))
async def list_groups(message: Message, user: User, session: AsyncSession):
    if not _is_admin(user):
        await message.answer("⛔ Нет прав.")
        return
    repo = GroupRepository(session)
    groups = await repo.get_all()
    if not groups:
        await message.answer("📋 Групп пока нет.")
        return
    lines = ["📋 <b>Группы:</b>\n"]
    for group in groups[:20]:
        status = "✅" if group.is_approved else "⏳"
        if group.is_banned:
            status = "🚫"
        lines.append(
            f"{status} <code>{group.telegram_group_id}</code> — "
            f"{group.group_name or 'без названия'}"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")
