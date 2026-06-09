from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import User, UserRole
from db.models.ticket import TicketStatus
from db.repositories.ticket_repo import TicketRepository
from db.repositories.user_repo import UserRepository
from db.repositories.group_repo import GroupRepository
from bot.keyboards.support_actions import get_support_taken_keyboard
from bot.utils.notify import notify_user_ticket_update

router = Router()


def _is_support(user: User) -> bool:
    return user.role in (UserRole.support, UserRole.admin, UserRole.superadmin)


async def _get_ticket_group(ticket, session: AsyncSession):
    """Загружает группу тикета если есть."""
    if not ticket.group_id:
        return None
    repo = GroupRepository(session)
    return await repo.get_by_id(ticket.group_id)


@router.callback_query(F.data.startswith("ticket:take:"))
async def take_ticket(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    bot: Bot,
):
    if not _is_support(user):
        await callback.answer("⛔ У вас нет прав.", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[2])
    ticket_repo = TicketRepository(session)
    ticket = await ticket_repo.get_by_id(ticket_id)

    if not ticket:
        await callback.answer("⚠️ Заявка не найдена.", show_alert=True)
        return

    if ticket.status != TicketStatus.new:
        await callback.answer("⚠️ Заявка уже обрабатывается.", show_alert=True)
        return

    await ticket_repo.assign(ticket, user.id)
    await ticket_repo.update_status(
        ticket, TicketStatus.in_progress,
        changed_by_id=user.id,
        comment=f"Взял в работу: {user.username or user.first_name}",
    )

    agent_name = f"@{user.username}" if user.username else user.first_name
    await callback.message.edit_text(
        callback.message.text + f"\n\n🔧 <b>Взял в работу:</b> {agent_name}",
        parse_mode="HTML",
        reply_markup=get_support_taken_keyboard(ticket_id),
    )

    # Уведомляем пользователя и группу
    user_repo = UserRepository(session)
    ticket_user = await user_repo.get_by_id(ticket.user_id)
    group = await _get_ticket_group(ticket, session)

    if ticket_user:
        await notify_user_ticket_update(
            bot, ticket_user, ticket,
            f"🔧 Ваша заявка <b>#{ticket.id}</b> взята в работу.\n"
            f"Мы работаем над решением.",
            group=group,
        )

    await callback.answer("✅ Заявка взята в работу.")


@router.callback_query(F.data.startswith("ticket:resolve:"))
async def resolve_ticket(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    bot: Bot,
):
    if not _is_support(user):
        await callback.answer("⛔ Нет прав.", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[2])
    ticket_repo = TicketRepository(session)
    ticket = await ticket_repo.get_by_id(ticket_id)

    if not ticket:
        await callback.answer("⚠️ Заявка не найдена.", show_alert=True)
        return

    await ticket_repo.update_status(
        ticket, TicketStatus.resolved,
        changed_by_id=user.id,
        comment="Решено",
    )

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>РЕШЕНО</b>",
        parse_mode="HTML",
    )

    user_repo = UserRepository(session)
    ticket_user = await user_repo.get_by_id(ticket.user_id)
    group = await _get_ticket_group(ticket, session)

    if ticket_user:
        await notify_user_ticket_update(
            bot, ticket_user, ticket,
            f"✅ Ваша заявка <b>#{ticket.id}</b> решена!\n"
            f"Если проблема осталась — создайте новую заявку.",
            group=group,
        )

    await callback.answer("✅ Заявка закрыта.")


@router.callback_query(F.data.startswith("ticket:reject:"))
async def reject_ticket(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    bot: Bot,
):
    if not _is_support(user):
        await callback.answer("⛔ Нет прав.", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[2])
    ticket_repo = TicketRepository(session)
    ticket = await ticket_repo.get_by_id(ticket_id)

    if not ticket:
        await callback.answer("⚠️ Заявка не найдена.", show_alert=True)
        return

    await ticket_repo.update_status(
        ticket, TicketStatus.rejected,
        changed_by_id=user.id,
    )

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <b>ОТКЛОНЕНО</b>",
        parse_mode="HTML",
    )

    user_repo = UserRepository(session)
    ticket_user = await user_repo.get_by_id(ticket.user_id)
    group = await _get_ticket_group(ticket, session)

    if ticket_user:
        await notify_user_ticket_update(
            bot, ticket_user, ticket,
            f"❌ Заявка <b>#{ticket.id}</b> отклонена.\n"
            f"По вопросам обратитесь к администратору.",
            group=group,
        )

    await callback.answer("Заявка отклонена.")


@router.callback_query(F.data.startswith("ticket:waiting:"))
async def waiting_ticket(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    bot: Bot,
):
    if not _is_support(user):
        await callback.answer("⛔ Нет прав.", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[2])
    ticket_repo = TicketRepository(session)
    ticket = await ticket_repo.get_by_id(ticket_id)

    if not ticket:
        await callback.answer("⚠️ Заявка не найдена.", show_alert=True)
        return

    await ticket_repo.update_status(
        ticket, TicketStatus.waiting_info,
        changed_by_id=user.id,
    )

    await callback.message.edit_text(
        callback.message.text + "\n\n❓ <b>Ожидание доп. информации</b>",
        parse_mode="HTML",
    )

    user_repo = UserRepository(session)
    ticket_user = await user_repo.get_by_id(ticket.user_id)
    group = await _get_ticket_group(ticket, session)

    if ticket_user:
        await notify_user_ticket_update(
            bot, ticket_user, ticket,
            f"❓ По заявке <b>#{ticket.id}</b> требуется дополнительная информация.\n"
            f"Пожалуйста, свяжитесь с администратором.",
            group=group,
        )

    await callback.answer("Статус обновлён.")
