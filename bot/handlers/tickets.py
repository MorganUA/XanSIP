from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from db.models.user import User
from db.models.sip_account import SipAccount, SipStatus
from db.models.ticket import ErrorType, TicketSource
from db.repositories.sip_repo import SipRepository
from db.repositories.ticket_repo import TicketRepository
from bot.fsm.states import TicketFSM
from bot.keyboards.sip_select import get_sip_select_keyboard
from bot.keyboards.error_types import get_error_type_keyboard, ERROR_TYPE_LABELS
from bot.keyboards.main_menu import get_main_menu
from bot.utils.notify import notify_support_new_ticket
from bot.config import settings

router = Router()


# ─── Антиспам хелперы ────────────────────────────────────────────────

async def check_cooldown(redis: Redis, user_id: int, sip_id: int) -> bool:
    """True = cooldown активен (нельзя создавать)."""
    key = f"cooldown:sip:{sip_id}:user:{user_id}"
    result = await redis.get(key)
    return result is not None


async def set_cooldown(redis: Redis, user_id: int, sip_id: int, minutes: int):
    key = f"cooldown:sip:{sip_id}:user:{user_id}"
    await redis.set(key, 1, ex=minutes * 60)


async def check_daily_limit(redis: Redis, user_id: int, max_tickets: int) -> bool:
    """True = лимит превышен."""
    key = f"daily_tickets:user:{user_id}"
    count = await redis.get(key)
    if count is None:
        return False
    return int(count) >= max_tickets


async def increment_daily_counter(redis: Redis, user_id: int):
    key = f"daily_tickets:user:{user_id}"
    pipe = redis.pipeline()
    await pipe.incr(key)
    await pipe.expire(key, 86400)
    await pipe.execute()


SIP_STATUS_LABELS = {
    SipStatus.active: "активен",
    SipStatus.frozen: "заморожен",
    SipStatus.disabled: "отключён",
}


async def validate_sip_for_new_ticket(
    *,
    redis: Redis,
    user: User,
    sip: SipAccount,
    session: AsyncSession,
) -> str | None:
    """Возвращает текст ошибки или None, если заявку можно создавать."""
    if sip.status != SipStatus.active:
        status = SIP_STATUS_LABELS.get(sip.status, sip.status.value)
        return f"⛔ SIP {sip.sip_number} недоступен (статус: {status})."

    ticket_repo = TicketRepository(session)
    open_ticket = await ticket_repo.get_open_by_sip(sip.id)
    if open_ticket:
        return (
            f"⚠️ По SIP {sip.sip_number} уже есть открытая заявка #{open_ticket.id}.\n"
            "Дождитесь её решения."
        )

    if await check_cooldown(redis, user.id, sip.id):
        return (
            f"⏳ Подождите {settings.cooldown_minutes} минут "
            "перед следующей заявкой по этому SIP."
        )

    if await check_daily_limit(redis, user.id, settings.max_tickets_per_day):
        return (
            f"⚠️ Вы достигли лимита заявок за сегодня "
            f"({settings.max_tickets_per_day})."
        )

    return None


# ─── Кнопка "Сообщить об ошибке" ─────────────────────────────────────

@router.message(F.text == "🚨 Сообщить об ошибке")
async def start_ticket_fsm(message: Message, user: User, state: FSMContext, session: AsyncSession):
    sip_repo = SipRepository(session)
    sips = await sip_repo.get_active_by_user_id(user.id)

    if not sips:
        await message.answer(
            "📞 У вас нет активных SIP-номеров.\n"
            "Обратитесь к администратору для подключения."
        )
        return

    await state.set_state(TicketFSM.selecting_sip)
    await message.answer(
        "📞 Выберите SIP-номер, по которому возникла проблема:",
        reply_markup=get_sip_select_keyboard(sips),
    )


# ─── FSM: выбор SIP ──────────────────────────────────────────────────

@router.callback_query(F.data.startswith("sip:select:"), TicketFSM.selecting_sip)
async def sip_selected(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    redis: Redis,
):
    sip_id = int(callback.data.split(":")[2])

    # Проверяем что SIP принадлежит пользователю
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
    await state.set_state(TicketFSM.selecting_error_type)

    await callback.message.edit_text(
        f"📞 SIP: <code>{sip.sip_number}</code>\n\n"
        "⚠️ Выберите тип ошибки:",
        parse_mode="HTML",
        reply_markup=get_error_type_keyboard(sip_id),
    )
    await callback.answer()


# ─── FSM: выбор типа ошибки ──────────────────────────────────────────

@router.callback_query(F.data.startswith("error:type:"), TicketFSM.selecting_error_type)
async def error_type_selected(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    sip_id = int(parts[2])
    error_type_str = parts[3]

    await state.update_data(error_type=error_type_str)

    if error_type_str == ErrorType.other.value:
        await state.set_state(TicketFSM.entering_description)
        await callback.message.edit_text(
            "💬 Опишите проблему своими словами:\n\n"
            "<i>Напишите подробное описание ошибки.</i>",
            parse_mode="HTML",
        )
    else:
        label = ERROR_TYPE_LABELS.get(ErrorType(error_type_str), error_type_str)
        await state.update_data(description=label)
        await state.set_state(TicketFSM.confirming)
        data = await state.get_data()
        await callback.message.edit_text(
            f"📋 <b>Подтвердите заявку:</b>\n\n"
            f"📞 SIP: <code>{data['sip_number']}</code>\n"
            f"⚠️ Ошибка: {label}\n\n"
            "Отправить заявку?",
            parse_mode="HTML",
            reply_markup=_confirm_keyboard(),
        )
    await callback.answer()


# ─── FSM: ввод описания (если "Другое") ──────────────────────────────

@router.message(TicketFSM.entering_description)
async def description_entered(message: Message, state: FSMContext):
    if len(message.text) < 5:
        await message.answer("⚠️ Описание слишком короткое. Напишите подробнее.")
        return
    if len(message.text) > 1000:
        await message.answer("⚠️ Описание слишком длинное (максимум 1000 символов).")
        return

    await state.update_data(description=message.text)
    await state.set_state(TicketFSM.confirming)
    data = await state.get_data()

    await message.answer(
        f"📋 <b>Подтвердите заявку:</b>\n\n"
        f"📞 SIP: <code>{data['sip_number']}</code>\n"
        f"⚠️ Ошибка: Другое\n"
        f"📝 Описание: {message.text}\n\n"
        "Отправить заявку?",
        parse_mode="HTML",
        reply_markup=_confirm_keyboard(),
    )


# ─── FSM: подтверждение и создание тикета ────────────────────────────

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
    await state.clear()

    sip_repo = SipRepository(session)
    ticket_repo = TicketRepository(session)

    sip = await sip_repo.get_by_id(data["sip_id"])
    error_type = ErrorType(data["error_type"])
    description = data["description"]

    ticket = await ticket_repo.create(
        user_id=user.id,
        sip_id=sip.id if sip else None,
        error_type=error_type,
        description=description,
        source=TicketSource.personal_chat,
    )

    # Устанавливаем cooldown и счётчик
    if sip:
        await set_cooldown(redis, user.id, sip.id, settings.cooldown_minutes)
    await increment_daily_counter(redis, user.id)

    # Уведомляем support
    msg_id = await notify_support_new_ticket(bot, ticket, user, sip)
    if msg_id:
        await ticket_repo.set_support_message_id(ticket, msg_id)

    await callback.message.edit_text(
        f"✅ <b>Заявка #{ticket.id} создана!</b>\n\n"
        "Наша команда поддержки уже получила уведомление.\n"
        "Мы сообщим вам об изменении статуса.",
        parse_mode="HTML",
    )
    await callback.answer()


# ─── Отмена FSM ──────────────────────────────────────────────────────

@router.callback_query(F.data == "ticket:cancel")
async def cancel_ticket(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Создание заявки отменено.")
    await callback.answer()


# ─── Команда /err ─────────────────────────────────────────────────────

@router.message(Command("err"))
async def cmd_err(
    message: Message,
    user: User,
    session: AsyncSession,
    bot: Bot,
    redis: Redis,
):
    """
    Формат: /err <sip_number> <описание>
    Пример: /err 100 busy here
    """
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer(
            "⚠️ Неверный формат команды.\n\n"
            "Используйте: <code>/err номер_сип описание</code>\n"
            "Пример: <code>/err 100 busy here</code>",
            parse_mode="HTML",
        )
        return

    sip_number = args[1]
    description = args[2]

    sip_repo = SipRepository(session)
    ticket_repo = TicketRepository(session)

    # Проверяем что SIP принадлежит пользователю
    sip = await sip_repo.get_by_number_and_user(sip_number, user.id)
    if not sip:
        await message.answer(
            f"⛔ SIP <code>{sip_number}</code> не найден в вашем аккаунте.",
            parse_mode="HTML",
        )
        return

    # Антиспам проверки
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

    msg_id = await notify_support_new_ticket(bot, ticket, user, sip)
    if msg_id:
        await ticket_repo.set_support_message_id(ticket, msg_id)

    await message.answer(
        f"✅ Заявка <b>#{ticket.id}</b> создана по SIP <code>{sip_number}</code>.\n"
        "Поддержка уже уведомлена.",
        parse_mode="HTML",
    )


# ─── Вспомогательная клавиатура подтверждения ────────────────────────

def _confirm_keyboard():
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить", callback_data="ticket:confirm")
    builder.button(text="❌ Отмена", callback_data="ticket:cancel")
    builder.adjust(2)
    return builder.as_markup()
