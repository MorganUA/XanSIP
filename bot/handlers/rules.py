from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

router = Router()

RULES_TEXT = """
📋 <b>Правила использования сервиса</b>

1. Один SIP-номер — одна заявка в работе одновременно.
2. Не создавайте дублирующие обращения по одной проблеме.
3. Описывайте проблему максимально подробно.
4. Оплата и заказ SIP производятся через администратора.
5. Не передавайте данные своих SIP третьим лицам.

По вопросам обращайтесь через кнопку <b>«Связь с админом»</b>.
""".strip()


@router.message(F.text == "📋 Правила")
@router.message(Command("rules"))
async def show_rules(message: Message):
    await message.answer(RULES_TEXT, parse_mode="HTML")
