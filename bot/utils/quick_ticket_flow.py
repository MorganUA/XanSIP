from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.group_errors import get_group_preset
from bot.fsm.states import TicketFSM
from bot.keyboards.main_menu import get_main_menu
from bot.keyboards.sip_select import get_sip_select_keyboard
from bot.utils.formatting import escape_html
from bot.utils.ticket_validation import validate_sip_for_new_ticket
from db.models.user import User
from db.repositories.sip_repo import SipRepository


def confirm_keyboard():
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить", callback_data="ticket:confirm")
    builder.button(text="❌ Отмена", callback_data="ticket:cancel")
    builder.adjust(2)
    return builder.as_markup()


def confirm_text(sip_number: str, error_label: str, description: str) -> str:
    return (
        f"📋 <b>Подтвердите заявку:</b>\n\n"
        f"📞 SIP: <code>{escape_html(sip_number)}</code>\n"
        f"⚠️ Ошибка: {escape_html(error_label)}\n"
        f"📝 {escape_html(description)}\n\n"
        "Отправить заявку?"
    )


async def show_confirm_message(
    target: Message,
    *,
    sip_number: str,
    error_label: str,
    description: str,
):
    await target.answer(
        confirm_text(sip_number, error_label, description),
        parse_mode="HTML",
        reply_markup=confirm_keyboard(),
    )


async def show_confirm_edit(
    target,
    *,
    sip_number: str,
    error_label: str,
    description: str,
):
    await target.edit_text(
        confirm_text(sip_number, error_label, description),
        parse_mode="HTML",
        reply_markup=confirm_keyboard(),
    )


async def begin_quick_ticket(
    message: Message,
    user: User,
    state: FSMContext,
    session: AsyncSession,
    redis: Redis,
    preset_id: str,
):
    preset = get_group_preset(preset_id)
    if not preset:
        await message.answer("⚠️ Неизвестный тип ошибки.")
        return

    sip_repo = SipRepository(session)
    sips = await sip_repo.get_active_by_user_id(user.id)
    if not sips:
        await message.answer(
            "📞 У вас нет активных SIP-номеров.\n"
            "Обратитесь к администратору для подключения.",
            reply_markup=get_main_menu(user),
        )
        return

    if len(sips) == 1:
        sip = sips[0]
        error = await validate_sip_for_new_ticket(
            redis=redis, user=user, sip=sip, session=session,
        )
        if error:
            await message.answer(error, reply_markup=get_main_menu(user))
            return
        await state.update_data(
            sip_id=sip.id,
            sip_number=sip.sip_number,
            error_type=preset.error_type.value,
            description=preset.label,
            error_label=preset.label,
        )
        await state.set_state(TicketFSM.confirming)
        await show_confirm_message(
            message,
            sip_number=sip.sip_number,
            error_label=preset.label,
            description=preset.label,
        )
        return

    await state.update_data(quick_preset_id=preset_id)
    await state.set_state(TicketFSM.selecting_sip)
    await message.answer(
        f"⚠️ <b>{escape_html(preset.label)}</b>\n\n"
        "📞 Выберите SIP-номер:",
        parse_mode="HTML",
        reply_markup=get_sip_select_keyboard(sips),
    )


async def apply_quick_preset_to_sip(
    callback: CallbackQuery,
    user: User,
    state: FSMContext,
    session: AsyncSession,
    redis: Redis,
    sip_id: int,
    preset_id: str,
) -> bool:
    """Returns True if confirm screen was shown."""
    preset = get_group_preset(preset_id)
    if not preset:
        await callback.answer("⚠️ Ошибка не найдена.", show_alert=True)
        return False

    sip_repo = SipRepository(session)
    sip = await sip_repo.get_by_id(sip_id)
    if not sip or sip.user_id != user.id:
        await callback.answer("⛔ SIP не найден.", show_alert=True)
        return False

    error = await validate_sip_for_new_ticket(
        redis=redis, user=user, sip=sip, session=session,
    )
    if error:
        await callback.answer(error, show_alert=True)
        return False

    await state.update_data(
        sip_id=sip.id,
        sip_number=sip.sip_number,
        error_type=preset.error_type.value,
        description=preset.label,
        error_label=preset.label,
    )
    await state.set_state(TicketFSM.confirming)
    await show_confirm_edit(
        callback.message,
        sip_number=sip.sip_number,
        error_label=preset.label,
        description=preset.label,
    )
    await callback.answer()
    return True
