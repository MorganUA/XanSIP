from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.support_actions import get_support_taken_keyboard
from bot.services.notification_config import get_notification_config, support_action_chat_ids
from bot.utils.notify import notify_user_ticket_update
from bot.utils.ticket_status import can_transition, transition_error
from bot.utils.ticket_status_messages import (
    build_ticket_status_message,
    ticket_status_notify_event,
)
from db.models.ticket import TicketStatus
from db.models.user import User, UserRole
from db.repositories.group_repo import GroupRepository
from db.repositories.ticket_repo import TicketRepository
from db.repositories.user_repo import UserRepository

router = Router()


def _is_support(user: User) -> bool:
    return user.role in (UserRole.support, UserRole.admin, UserRole.superadmin)


async def _is_support_chat(callback: CallbackQuery, session: AsyncSession) -> bool:
    config = await get_notification_config(session)
    return callback.message.chat.id in support_action_chat_ids(config)


async def _get_ticket_group(ticket, session: AsyncSession):
    if not ticket.group_id:
        return None
    repo = GroupRepository(session)
    return await repo.get_by_id(ticket.group_id)


async def _guard_support_action(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
) -> bool:
    if not _is_support(user):
        await callback.answer("⛔ У вас нет прав.", show_alert=True)
        return False
    if not await _is_support_chat(callback, session):
        await callback.answer("⛔ Действие доступно только в чате поддержки.", show_alert=True)
        return False
    return True


@router.callback_query(F.data.startswith("ticket:take:"))
async def take_ticket(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    bot: Bot,
):
    if not await _guard_support_action(callback, user, session):
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

    ticket_user = await UserRepository(session).get_by_id(ticket.user_id)
    group = await _get_ticket_group(ticket, session)
    if ticket_user:
        await notify_user_ticket_update(
            bot, ticket_user, ticket,
            build_ticket_status_message(ticket.id, TicketStatus.in_progress),
            group=group,
            session=session,
        )

    await callback.answer("✅ Заявка взята в работу.")


@router.callback_query(F.data.startswith("ticket:resolve:"))
async def resolve_ticket(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    bot: Bot,
):
    if not await _guard_support_action(callback, user, session):
        return

    ticket_id = int(callback.data.split(":")[2])
    ticket_repo = TicketRepository(session)
    ticket = await ticket_repo.get_by_id(ticket_id)

    if not ticket:
        await callback.answer("⚠️ Заявка не найдена.", show_alert=True)
        return

    if ticket.status == TicketStatus.resolved:
        await callback.answer("✅ Заявка уже решена.")
        return

    if not can_transition(ticket.status, TicketStatus.resolved):
        await callback.answer(
            transition_error(ticket.status, TicketStatus.resolved) or "Нельзя закрыть заявку.",
            show_alert=True,
        )
        return

    await ticket_repo.update_status(
        ticket, TicketStatus.resolved,
        changed_by_id=user.id,
        comment="Решено",
    )

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>РЕШЕНО</b>",
        parse_mode="HTML",
        reply_markup=None,
    )

    ticket_user = await UserRepository(session).get_by_id(ticket.user_id)
    group = await _get_ticket_group(ticket, session)
    if ticket_user:
        await notify_user_ticket_update(
            bot, ticket_user, ticket,
            build_ticket_status_message(ticket.id, TicketStatus.resolved),
            group=group,
            session=session,
            event=ticket_status_notify_event(TicketStatus.resolved),
        )

    await callback.answer("✅ Заявка закрыта.")


@router.callback_query(F.data.startswith("ticket:reject:"))
async def reject_ticket(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    bot: Bot,
):
    if not await _guard_support_action(callback, user, session):
        return

    ticket_id = int(callback.data.split(":")[2])
    ticket_repo = TicketRepository(session)
    ticket = await ticket_repo.get_by_id(ticket_id)

    if not ticket:
        await callback.answer("⚠️ Заявка не найдена.", show_alert=True)
        return

    if ticket.status == TicketStatus.rejected:
        await callback.answer("Заявка уже отклонена.")
        return

    if not can_transition(ticket.status, TicketStatus.rejected):
        await callback.answer(
            transition_error(ticket.status, TicketStatus.rejected) or "Заявка уже закрыта.",
            show_alert=True,
        )
        return

    await ticket_repo.update_status(
        ticket, TicketStatus.rejected,
        changed_by_id=user.id,
    )

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <b>ОТКЛОНЕНО</b>",
        parse_mode="HTML",
        reply_markup=None,
    )

    ticket_user = await UserRepository(session).get_by_id(ticket.user_id)
    group = await _get_ticket_group(ticket, session)
    if ticket_user:
        await notify_user_ticket_update(
            bot, ticket_user, ticket,
            build_ticket_status_message(ticket.id, TicketStatus.rejected),
            group=group,
            session=session,
        )

    await callback.answer("Заявка отклонена.")


@router.callback_query(F.data.startswith("ticket:waiting:"))
async def waiting_ticket(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    bot: Bot,
):
    if not await _guard_support_action(callback, user, session):
        return

    ticket_id = int(callback.data.split(":")[2])
    ticket_repo = TicketRepository(session)
    ticket = await ticket_repo.get_by_id(ticket_id)

    if not ticket:
        await callback.answer("⚠️ Заявка не найдена.", show_alert=True)
        return

    if ticket.status == TicketStatus.waiting_info:
        await callback.answer("Статус уже «ожидание информации».")
        return

    if not can_transition(ticket.status, TicketStatus.waiting_info):
        await callback.answer(
            transition_error(ticket.status, TicketStatus.waiting_info) or "Нельзя запросить информацию.",
            show_alert=True,
        )
        return

    await ticket_repo.update_status(
        ticket, TicketStatus.waiting_info,
        changed_by_id=user.id,
    )

    await callback.message.edit_text(
        callback.message.text + "\n\n❓ <b>Ожидание доп. информации</b>",
        parse_mode="HTML",
    )

    ticket_user = await UserRepository(session).get_by_id(ticket.user_id)
    group = await _get_ticket_group(ticket, session)
    if ticket_user:
        await notify_user_ticket_update(
            bot, ticket_user, ticket,
            build_ticket_status_message(ticket.id, TicketStatus.waiting_info),
            group=group,
            session=session,
        )

    await callback.answer("Статус обновлён.")
