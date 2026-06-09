from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

router = Router()

# Сюда вставь username своего админского аккаунта
ADMIN_USERNAME = "@tenguwar"

ADMIN_CONTACT_TEXT = (
    "👨‍💼 <b>Связь с администратором</b>\n\n"
    f"Для заказа SIP-номеров и оплаты услуг напишите: {ADMIN_USERNAME}\n\n"
    "📌 При обращении укажите ваш ID — нажмите кнопку <b>🆔 Мой ID</b>"
)

HELP_TEXT = (
    "ℹ️ <b>Помощь</b>\n\n"
    "🔹 /start — перезапустить бота\n"
    "🔹 /profile — ваш профиль\n"
    "🔹 /myid — ваш внутренний ID\n"
    "🔹 /mysip — ваши SIP-номера\n"
    "🔹 /err номер описание — быстро сообщить об ошибке\n"
    "🔹 /rules — правила использования\n\n"
    "По вопросам: " + ADMIN_USERNAME
)


@router.message(F.text == "👨‍💼 Связь с админом")
@router.message(Command("admin"))
async def admin_contact(message: Message):
    await message.answer(ADMIN_CONTACT_TEXT, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(HELP_TEXT, parse_mode="HTML")
