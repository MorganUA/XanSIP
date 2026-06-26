from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from db.models.user import User
from db.models.sip_account import SipStatus
from db.repositories.sip_repo import SipRepository
from db.repositories.ticket_repo import TicketRepository
from bot.fsm.states import TicketFSM
from bot.keyboards.sip_menu import (
    format_sip_list_text,
    format_sip_detail_text,
    get_sip_list_keyboard,
    get_sip_detail_keyboard,
)
from bot.keyboards.error_types import get_error_type_keyboard
from bot.keyboards.main_menu import get_main_menu
from bot.handlers.tickets import validate_sip_for_new_ticket

router = Router()


async def _load_user_sips(session: AsyncSession, user_id: int):
    repo = SipRepository(session)
    return await repo.get_by_user_id(user_id)


async def _render_sip_list(message_or_callback, sips, *, edit: bool = False):
    text = format_sip_list_text(sips)
    keyboard = get_sip_list_keyboard(sips)

    if edit:
        await message_or_callback.edit_text(
            text, parse_mode="HTML", reply_markup=keyboard,
        )
    else:
        await message_or_callback.answer(
            text, parse_mode="HTML", reply_markup=keyboard,
        )


@router.message(F.text == "📞 Мои SIP")
@router.message(Command("mysip"))
async def show_my_sip(message: Message, user: User, session: AsyncSession):
    sips = await _load_user_sips(session, user.id)

    if not sips:
        await message.answer(
            "📞 У вас пока нет подключённых SIP-номеров.\n\n"
            "Обратитесь к администратору для подключения.\n"
            "Ваш ID: нажмите кнопку <b>🆔 Мой ID</b>.",
            parse_mode="HTML",
            reply_markup=get_main_menu(),
        )
        return

    await _render_sip_list(message, sips)


@router.callback_query(F.data == "sip:refresh")
async def refresh_sip_list(callback: CallbackQuery, user: User, session: AsyncSession):
    sips = await _load_user_sips(session, user.id)
    if not sips:
        await callback.message.edit_text(
            "📞 У вас пока нет подключённых SIP-номеров.",
        )
        await callback.answer()
        return

    await _render_sip_list(callback.message, sips, edit=True)
    await callback.answer("🔄 Список обновлён")


@router.callback_query(F.data == "sip:back")
async def back_to_sip_list(callback: CallbackQuery, user: User, session: AsyncSession):
    sips = await _load_user_sips(session, user.id)
    if not sips:
        await callback.message.edit_text("📞 SIP-номера не найдены.")
        await callback.answer()
        return

    await _render_sip_list(callback.message, sips, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("sip:view:"))
async def view_sip_detail(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
):
    sip_id = int(callback.data.split(":")[2])

    sip_repo = SipRepository(session)
    sip = await sip_repo.get_by_id(sip_id)
    if not sip or sip.user_id != user.id:
        await callback.answer("⛔ SIP не найден.", show_alert=True)
        return

    ticket_repo = TicketRepository(session)
    open_ticket = await ticket_repo.get_open_by_sip(sip.id)
    can_report = (
        sip.status == SipStatus.active
        and open_ticket is None
    )

    await callback.message.edit_text(
        format_sip_detail_text(sip, open_ticket),
        parse_mode="HTML",
        reply_markup=get_sip_detail_keyboard(sip.id, can_report=can_report),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sip:report:"))
async def report_error_for_sip(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    state: FSMContext,
    redis: Redis,
):
    sip_id = int(callback.data.split(":")[2])

    sip_repo = SipRepository(session)
    sip = await sip_repo.get_by_id(sip_id)
    if not sip or sip.user_id != user.id:
        await callback.answer("⛔ SIP не найден.", show_alert=True)
        return

    error = await validate_sip_for_new_ticket(
        redis=redis, user=user, sip=sip, session=session,
    )
    if error:
        await callback.answer(error, show_alert=True)
        return

    await state.update_data(sip_id=sip.id, sip_number=sip.sip_number)
    await state.set_state(TicketFSM.selecting_error_type)

    await callback.message.edit_text(
        f"📞 SIP: <code>{sip.sip_number}</code>\n\n"
        "⚠️ Выберите тип ошибки:",
        parse_mode="HTML",
        reply_markup=get_error_type_keyboard(sip.id),
    )
    await callback.answer()
