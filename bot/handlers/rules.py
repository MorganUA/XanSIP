from aiogram import F, Router
from aiogram.types import Message
from aiogram.filters import Command

from bot.catalog.group_errors import GROUP_ERROR_PRESETS, MAIN_PRESET_IDS
from bot.filters.chat import apply_private_chat_filter
from bot.keyboards.main_menu import get_main_menu
from bot.utils.menu_catalog import BTN_ADMIN, BTN_MY_TICKETS, BTN_REPORT, BTN_RULES, BTN_TOPUP, TEXTS_RULES
from bot.utils.quick_errors import OTHER_ERROR_BUTTON
from db.models.user import User

router = apply_private_chat_filter(Router())

_quick = ", ".join(GROUP_ERROR_PRESETS[pid].button for pid in MAIN_PRESET_IDS)

RULES_TEXT = f"""
<b>Правила сервиса</b>

<b>Личный чат</b>
1. Быстрые заявки: {_quick}.
2. Полный каталог — <b>{OTHER_ERROR_BUTTON}</b> или <b>{BTN_REPORT}</b>.
3. <b>{BTN_MY_TICKETS}</b> — статус заявок.
4. На один SIP — одна открытая заявка.

<b>Группа колл-центра</b>
1. <code>/err номер_sip</code> → выбор типа проблемы.
2. <code>/status</code> — активные заявки · <code>/sips</code> — SIP владельца.
3. Кнопки личного меню в группе недоступны — бот подскажет альтернативу.
4. После решения заявки бот уведомит группу.

<b>Финансы и SIP</b>
• Пополнение USDT — <b>{BTN_TOPUP}</b>; проверка в Web CRM → Финансы.
• Заказ и подключение SIP — <b>{BTN_ADMIN}</b>.
• Не передавайте данные SIP третьим лицам.
""".strip()


@router.message(F.text.in_(TEXTS_RULES))
@router.message(Command("rules"))
async def show_rules(message: Message, user: User):
    await message.answer(
        RULES_TEXT,
        parse_mode="HTML",
        reply_markup=get_main_menu(user),
    )
