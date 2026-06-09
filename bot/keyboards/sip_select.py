from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models.sip_account import SipAccount, SipStatus


def get_sip_select_keyboard(sips: list[SipAccount]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for sip in sips:
        status_icon = {
            SipStatus.active: "🟢",
            SipStatus.frozen: "🟡",
            SipStatus.disabled: "🔴",
        }.get(sip.status, "⚪")

        label = f"{status_icon} SIP {sip.sip_number}"
        if sip.description:
            label += f" — {sip.description}"

        builder.button(
            text=label,
            callback_data=f"sip:select:{sip.id}",
        )

    builder.button(text="❌ Отмена", callback_data="ticket:cancel")
    builder.adjust(1)
    return builder.as_markup()
