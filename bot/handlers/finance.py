from decimal import Decimal

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from services.finance_service import (
    FinanceError,
    create_usdt_deposit,
    get_user_balance,
    mark_deposit_paid,
)
from bot.filters.chat import apply_private_chat_filter
from bot.fsm.states import FinanceFSM
from bot.keyboards.main_menu import get_main_menu
from bot.services.finance_config import get_finance_config
from bot.utils.fsm_menu_guard import cancel_fsm_for_menu_button
from bot.utils.menu_catalog import BTN_BALANCE, BTN_TOPUP, TEXTS_BALANCE, TEXTS_TOPUP
from db.models.user import User
from db.repositories.finance_repo import FinanceRepository

router = apply_private_chat_filter(Router())


def _paid_keyboard(deposit_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я оплатил", callback_data=f"fin:paid:{deposit_id}")
    builder.button(text="❌ Отмена", callback_data=f"fin:cancel:{deposit_id}")
    builder.adjust(1)
    return builder.as_markup()


async def _format_balance(session: AsyncSession, user: User) -> str:
    balance = await get_user_balance(session, user.id)
    return f"<b>Баланс:</b> <code>{balance}</code> USDT"


@router.message(F.text.in_(TEXTS_BALANCE))
@router.message(Command("balance"))
async def show_balance(message: Message, user: User, session: AsyncSession):
    text = await _format_balance(session, user)
    await message.answer(
        f"{text}\n\nДля пополнения нажмите <b>{BTN_TOPUP}</b>",
        parse_mode="HTML",
        reply_markup=get_main_menu(user),
    )


@router.message(F.text.in_(TEXTS_TOPUP))
@router.message(Command("deposit"))
async def start_topup(message: Message, user: User, state: FSMContext, session: AsyncSession):
    cfg = await get_finance_config(session)
    balance_line = await _format_balance(session, user)
    await state.set_state(FinanceFSM.entering_amount)
    await message.answer(
        f"{balance_line}\n\n"
        f"<b>Пополнение USDT</b>\n"
        f"Введите сумму ({cfg['min_deposit_usdt']}–{cfg['max_deposit_usdt']} USDT):\n\n"
        f"<i>{cfg.get('instruction_text', '')}</i>",
        parse_mode="HTML",
        reply_markup=get_main_menu(user),
    )


@router.message(FinanceFSM.entering_amount)
async def amount_entered(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if await cancel_fsm_for_menu_button(
        message, user, state, session, cancel_note="Пополнение отменено.",
    ):
        return
    if not message.text:
        await message.answer("⚠️ Введите число — сумму в USDT.")
        return
    try:
        deposit = await create_usdt_deposit(session, user, message.text)
    except FinanceError as exc:
        await message.answer(f"❌ {exc}", reply_markup=get_main_menu(user))
        return

    wallet = deposit.wallet
    if not wallet:
        repo = FinanceRepository(session)
        wallet = await repo.get_wallet(deposit.wallet_id)

    cfg = await get_finance_config(session)
    await state.update_data(deposit_id=deposit.id)
    await state.set_state(FinanceFSM.entering_tx_hash)

    expires = deposit.expires_at.strftime("%d.%m.%Y %H:%M UTC") if deposit.expires_at else "—"
    await message.answer(
        f"✅ <b>Заявка #{deposit.id}</b>\n\n"
        f"Сумма: <code>{deposit.amount_usdt}</code> USDT\n"
        f"Сеть: <b>{wallet.network}</b>\n"
        f"Адрес:\n<code>{wallet.address}</code>\n\n"
        f"⏱ Действует до: {expires}\n\n"
        f"{cfg.get('instruction_text', '')}",
        parse_mode="HTML",
        reply_markup=_paid_keyboard(deposit.id),
    )


@router.callback_query(F.data.startswith("fin:paid:"))
async def deposit_paid_cb(callback: CallbackQuery, user: User, state: FSMContext):
    deposit_id = int(callback.data.split(":")[2])
    await state.update_data(deposit_id=deposit_id)
    await state.set_state(FinanceFSM.entering_tx_hash)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "📝 Укажите TX hash транзакции (или отправьте <code>-</code> чтобы пропустить):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("fin:cancel:"))
async def deposit_cancel_cb(callback: CallbackQuery, user: User, state: FSMContext, session: AsyncSession):
    deposit_id = int(callback.data.split(":")[2])
    repo = FinanceRepository(session)
    deposit = await repo.get_deposit(deposit_id)
    if deposit and deposit.user_id == user.id:
        from db.models.finance import DepositStatus
        await repo.update_deposit(deposit, status=DepositStatus.cancelled)
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("❌ Заявка отменена.", reply_markup=get_main_menu(user))
    await callback.answer()


@router.message(FinanceFSM.entering_tx_hash)
async def tx_hash_entered(message: Message, user: User, state: FSMContext, session: AsyncSession):
    if await cancel_fsm_for_menu_button(
        message, user, state, session, cancel_note="Пополнение отменено.",
    ):
        return
    data = await state.get_data()
    deposit_id = data.get("deposit_id")
    if not deposit_id:
        await state.clear()
        await message.answer("⚠️ Сессия истекла. Начните снова.", reply_markup=get_main_menu(user))
        return

    tx = None if message.text and message.text.strip() == "-" else (message.text or "").strip()
    try:
        deposit = await mark_deposit_paid(session, user, deposit_id, tx_hash=tx)
    except FinanceError as exc:
        await message.answer(f"❌ {exc}", reply_markup=get_main_menu(user))
        await state.clear()
        return

    await state.clear()
    balance = await get_user_balance(session, user.id)
    await message.answer(
        f"📨 Заявка <b>#{deposit.id}</b> отправлена на проверку.\n"
        f"Текущий баланс: <code>{balance}</code> USDT\n"
        "После подтверждения администратором средства поступят на счёт.",
        parse_mode="HTML",
        reply_markup=get_main_menu(user),
    )
