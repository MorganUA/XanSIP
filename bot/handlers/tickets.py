from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.catalog.errors import (
    CATEGORY_LABELS,
    ErrorCategory,
    get_preset,
)
from bot.catalog.group_errors import get_group_preset
from bot.filters.chat import apply_private_chat_filter
from bot.fsm.states import TicketFSM
from bot.keyboards.error_types import (
    get_error_category_keyboard,
    get_error_presets_keyboard,
)
from bot.keyboards.private_err import (
    get_private_error_keyboard,
    get_private_submenu_keyboard,
)
from bot.keyboards.main_menu import get_main_menu
from bot.keyboards.sip_select import get_sip_select_keyboard
from bot.utils.menu_catalog import BTN_ADMIN, BTN_MINI_APP, BTN_REPORT, TEXTS_REPORT
from bot.utils.fsm_menu_guard import cancel_fsm_for_menu_button
from bot.utils.webapp import get_mini_app_url
from bot.utils.formatting import escape_html
from bot.utils.notify import notify_support_new_ticket
from bot.utils.quick_errors import OTHER_ERROR_BUTTON, preset_id_from_button, quick_error_button_texts
from bot.utils.quick_ticket_flow import (
    apply_quick_preset_to_sip,
    begin_quick_ticket,
    show_confirm_edit as _show_confirm_edit,
    show_confirm_message as _show_confirm_message,
)
from bot.utils.ticket_validation import (
    increment_daily_counter,
    set_cooldown,
    validate_sip_for_new_ticket,
)
from db.models.ticket import ErrorType, TicketSource
from db.models.user import User
from db.repositories.sip_repo import SipRepository
from db.repositories.ticket_repo import TicketRepository

router = apply_private_chat_filter(Router())


def _ticket_success_text(ticket_id: int, *, support_notified: bool) -> str:
    if support_notified:
        return (
            f"✅ <b>Заявка #{ticket_id} создана!</b>\n\n"
            "Наша команда поддержки уже получила уведомление.\n"
            "Мы сообщим вам об изменении статуса."
        )
    return (
        f"✅ <b>Заявка #{ticket_id} создана!</b>\n\n"
        "⚠️ Не удалось уведомить поддержку автоматически.\n"
        "Сообщите администратору номер заявки."
    )


async def _show_confirm(
    target,
    *,
    sip_number: str,
    error_label: str,
    description: str,
    edit: bool = False,
):
    if edit:
        await _show_confirm_edit(
            target, sip_number=sip_number, error_label=error_label, description=description,
        )
    else:
        await _show_confirm_message(
            target, sip_number=sip_number, error_label=error_label, description=description,
        )


@router.message(F.text.in_(TEXTS_REPORT))
async def open_report_menu(message: Message, user: User):
    mini = f"\nИли откройте <b>{BTN_MINI_APP}</b>." if get_mini_app_url() else ""
    await message.answer(
        f"<b>{BTN_REPORT}</b>\n\n"
        f"Выберите тип проблемы:{mini}",
        parse_mode="HTML",
        reply_markup=get_private_error_keyboard(),
    )


@router.callback_query(F.data.startswith("perr:"))
async def private_err_callback(
    callback: CallbackQuery,
    user: User,
    state: FSMContext,
    session: AsyncSession,
    redis: Redis,
):
    parts = callback.data.split(":")
    action = parts[1]

    if action == "more":
        await callback.message.edit_reply_markup(reply_markup=get_private_submenu_keyboard())
        await callback.answer()
        return
    if action == "back":
        await callback.message.edit_reply_markup(reply_markup=get_private_error_keyboard())
        await callback.answer()
        return
    if action == "cancel":
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Отменено")
        return
    if action == "catalog":
        await callback.message.edit_reply_markup(reply_markup=None)
        await start_ticket_fsm(callback.message, user, state, session)
        await callback.answer()
        return
    if action not in ("m", "s"):
        await callback.answer()
        return

    preset_id = parts[2]
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await begin_quick_ticket(callback.message, user, state, session, redis, preset_id)


@router.message(F.text.in_(quick_error_button_texts()))
async def quick_error_from_menu(
    message: Message,
    user: User,
    state: FSMContext,
    session: AsyncSession,
    redis: Redis,
):
    preset_id = preset_id_from_button(message.text)
    if preset_id:
        await begin_quick_ticket(message, user, state, session, redis, preset_id)


@router.message(F.text == OTHER_ERROR_BUTTON)
async def start_ticket_fsm(message: Message, user: User, state: FSMContext, session: AsyncSession):
    sip_repo = SipRepository(session)
    sips = await sip_repo.get_active_by_user_id(user.id)

    if not sips:
        await message.answer(
            "Нет активных SIP-номеров.\n"
            f"Обратитесь в <b>{BTN_ADMIN}</b> для подключения."
        )
        return

    await state.set_state(TicketFSM.selecting_sip)
    await message.answer(
        "Выберите SIP-номер, по которому возникла проблема:",
        reply_markup=get_sip_select_keyboard(sips),
    )


@router.callback_query(F.data.startswith("sip:select:"), TicketFSM.selecting_sip)
async def sip_selected(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    redis: Redis,
):
    sip_id = int(callback.data.split(":")[2])
    sip_repo = SipRepository(session)
    sip = await sip_repo.get_by_id(sip_id)
    if not sip or sip.user_id != user.id:
        await callback.answer("⛔ Этот SIP вам не принадлежит.", show_alert=True)
        return

    error = await validate_sip_for_new_ticket(
        redis=redis, user=user, sip=sip, session=session,
    )
    if error:
        await callback.answer(error, show_alert=True)
        await state.clear()
        return

    await state.update_data(sip_id=sip_id, sip_number=sip.sip_number)
    data = await state.get_data()
    quick_preset_id = data.get("quick_preset_id")

    if quick_preset_id:
        preset = get_group_preset(quick_preset_id)
        if not preset:
            await state.clear()
            await callback.answer("⚠️ Ошибка не найдена.", show_alert=True)
            return
        await state.update_data(
            error_type=preset.error_type.value,
            description=preset.label,
            error_label=preset.label,
            quick_preset_id=None,
        )
        await state.set_state(TicketFSM.confirming)
        await _show_confirm(
            callback.message,
            sip_number=sip.sip_number,
            error_label=preset.label,
            description=preset.label,
            edit=True,
        )
        await callback.answer()
        return

    await state.set_state(TicketFSM.selecting_error_type)
    await callback.message.edit_text(
        f"📞 SIP: <code>{escape_html(sip.sip_number)}</code>\n\n"
        "⚠️ Выберите категорию ошибки:",
        parse_mode="HTML",
        reply_markup=get_error_category_keyboard(sip_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("error:cat:"), TicketFSM.selecting_error_type)
async def error_category_selected(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    sip_id = int(parts[2])
    category = ErrorCategory(parts[3])
    data = await state.get_data()

    await state.set_state(TicketFSM.selecting_error_preset)
    await callback.message.edit_text(
        f"📞 SIP: <code>{escape_html(data['sip_number'])}</code>\n\n"
        f"{CATEGORY_LABELS[category]}\n"
        "Выберите ошибку из списка:",
        parse_mode="HTML",
        reply_markup=get_error_presets_keyboard(category, page=0, sip_id=sip_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("error:page:"), TicketFSM.selecting_error_preset)
async def error_preset_page(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    sip_id = int(parts[2])
    category = ErrorCategory(parts[3])
    page = int(parts[4])
    data = await state.get_data()

    await callback.message.edit_text(
        f"📞 SIP: <code>{escape_html(data['sip_number'])}</code>\n\n"
        f"{CATEGORY_LABELS[category]}\n"
        "Выберите ошибку из списка:",
        parse_mode="HTML",
        reply_markup=get_error_presets_keyboard(category, page=page, sip_id=sip_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("error:back:"), TicketFSM.selecting_error_preset)
async def error_back_to_categories(callback: CallbackQuery, state: FSMContext):
    sip_id = int(callback.data.split(":")[2])
    data = await state.get_data()
    await state.set_state(TicketFSM.selecting_error_type)
    await callback.message.edit_text(
        f"📞 SIP: <code>{escape_html(data['sip_number'])}</code>\n\n"
        "⚠️ Выберите категорию ошибки:",
        parse_mode="HTML",
        reply_markup=get_error_category_keyboard(sip_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("error:preset:"), TicketFSM.selecting_error_preset)
async def error_preset_selected(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    preset_id = parts[3]
    preset = get_preset(preset_id)
    if not preset:
        await callback.answer("⚠️ Ошибка не найдена.", show_alert=True)
        return

    error_label = f"{CATEGORY_LABELS[preset.category]} → {preset.title}"
    await state.update_data(
        error_type=preset.error_type.value,
        description=preset.description,
        error_label=error_label,
    )
    await state.set_state(TicketFSM.confirming)
    data = await state.get_data()
    await _show_confirm(
        callback.message,
        sip_number=data["sip_number"],
        error_label=error_label,
        description=preset.description,
        edit=True,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("error:type:"), TicketFSM.selecting_error_type)
async def error_type_selected(callback: CallbackQuery, state: FSMContext):
    error_type_str = callback.data.split(":")[3]
    if error_type_str != ErrorType.other.value:
        await callback.answer("⚠️ Выберите ошибку из справочника.", show_alert=True)
        return

    await state.update_data(error_type=error_type_str, error_label="💬 Другое")
    await state.set_state(TicketFSM.entering_description)
    await callback.message.edit_text(
        "💬 Опишите проблему своими словами:\n\n"
        "<i>Напишите подробное описание ошибки.</i>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(TicketFSM.entering_description)
async def description_entered(message: Message, state: FSMContext, user: User, session: AsyncSession):
    if await cancel_fsm_for_menu_button(
        message, user, state, session, cancel_note="Создание заявки отменено.",
    ):
        return
    if not message.text:
        await message.answer("⚠️ Отправьте текстовое описание проблемы.")
        return
    if len(message.text) < 5:
        await message.answer("⚠️ Описание слишком короткое. Напишите подробнее.")
        return
    if len(message.text) > 1000:
        await message.answer("⚠️ Описание слишком длинное (максимум 1000 символов).")
        return

    await state.update_data(description=message.text)
    await state.set_state(TicketFSM.confirming)
    data = await state.get_data()
    await _show_confirm(
        message,
        sip_number=data["sip_number"],
        error_label="Другое",
        description=message.text,
    )


@router.callback_query(F.data == "ticket:confirm", TicketFSM.confirming)
async def confirm_ticket(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    bot: Bot,
    redis: Redis,
):
    data = await state.get_data()
    sip_repo = SipRepository(session)
    ticket_repo = TicketRepository(session)

    sip = await sip_repo.get_by_id(data["sip_id"])
    if not sip or sip.user_id != user.id:
        await state.clear()
        await callback.answer("⛔ SIP не найден.", show_alert=True)
        return

    error = await validate_sip_for_new_ticket(
        redis=redis, user=user, sip=sip, session=session,
    )
    if error:
        await state.clear()
        await callback.answer(error, show_alert=True)
        return

    error_label = data.get("error_label")
    await state.clear()
    ticket = await ticket_repo.create(
        user_id=user.id,
        sip_id=sip.id,
        error_type=ErrorType(data["error_type"]),
        description=data["description"],
        source=TicketSource.personal_chat,
    )

    await set_cooldown(redis, user.id, sip.id, settings.cooldown_minutes)
    await increment_daily_counter(redis, user.id)

    msg_id = await notify_support_new_ticket(
        bot, ticket, user, sip, error_label=error_label, session=session,
    )
    if msg_id:
        await ticket_repo.set_support_message_id(ticket, msg_id)

    await callback.message.edit_text(
        _ticket_success_text(ticket.id, support_notified=msg_id is not None),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "ticket:cancel")
async def cancel_ticket(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Создание заявки отменено.")
    await callback.answer()


@router.message(Command("err"))
async def cmd_err(
    message: Message,
    user: User,
    session: AsyncSession,
    bot: Bot,
    redis: Redis,
):
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer(
            "ℹ️ Рекомендуем: быстрые кнопки <b>Фрод / Баланс / Недозвон</b> "
            f"или <b>{OTHER_ERROR_BUTTON}</b>.\n\n"
            "Быстрая команда:\n"
            "<code>/err номер_сип описание</code>\n"
            "Пример: <code>/err 100 нет регистрации</code>",
            parse_mode="HTML",
            reply_markup=get_main_menu(user),
        )
        return

    sip_number = args[1]
    description = args[2]
    sip_repo = SipRepository(session)
    ticket_repo = TicketRepository(session)

    sip = await sip_repo.get_by_number_and_user(sip_number, user.id)
    if not sip:
        await message.answer(
            f"⛔ SIP <code>{escape_html(sip_number)}</code> не найден в вашем аккаунте.",
            parse_mode="HTML",
        )
        return

    error = await validate_sip_for_new_ticket(
        redis=redis, user=user, sip=sip, session=session,
    )
    if error:
        await message.answer(error)
        return

    ticket = await ticket_repo.create(
        user_id=user.id,
        sip_id=sip.id,
        error_type=ErrorType.other,
        description=description,
        source=TicketSource.command,
    )

    await set_cooldown(redis, user.id, sip.id, settings.cooldown_minutes)
    await increment_daily_counter(redis, user.id)

    msg_id = await notify_support_new_ticket(
        bot, ticket, user, sip,
        error_label=f"💬 Команда /err: {description[:80]}",
        session=session,
    )
    if msg_id:
        await ticket_repo.set_support_message_id(ticket, msg_id)

    await message.answer(
        _ticket_success_text(ticket.id, support_notified=msg_id is not None),
        parse_mode="HTML",
        reply_markup=get_main_menu(user),
    )
