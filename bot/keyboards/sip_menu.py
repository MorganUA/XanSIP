from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.catalog.group_errors import GROUP_ERROR_PRESETS, MAIN_PRESET_IDS
from bot.utils.quick_errors import OTHER_ERROR_BUTTON
from db.models.sip_account import SipAccount, SipStatus
from db.models.ticket import Ticket, TicketStatus

STATUS_ICONS = {
    SipStatus.active: "🟢",
    SipStatus.frozen: "🟡",
    SipStatus.disabled: "🔴",
}

STATUS_LABELS = {
    SipStatus.active: "Активен",
    SipStatus.frozen: "Заморожен",
    SipStatus.disabled: "Отключён",
}

TICKET_STATUS_LABELS = {
    TicketStatus.new: "🆕 Новая",
    TicketStatus.in_progress: "🔧 В работе",
    TicketStatus.waiting_info: "❓ Нужна информация",
    TicketStatus.resolved: "✅ Решена",
    TicketStatus.rejected: "❌ Отклонена",
    TicketStatus.closed: "🔒 Закрыта",
}


def format_sip_list_text(sips: list[SipAccount]) -> str:
    lines = [
        "📞 <b>Ваши SIP-номера</b>\n",
        f"Всего: {len(sips)}",
        "Выберите номер или сообщите об ошибке кнопками ниже.\n",
    ]
    for sip in sips:
        icon = STATUS_ICONS.get(sip.status, "⚪")
        label = STATUS_LABELS.get(sip.status, "Неизвестно")
        line = f"{icon} <code>{sip.sip_number}</code> — {label}"
        if sip.description:
            line += f"\n   📝 {sip.description}"
        lines.append(line)
    return "\n".join(lines)


def format_sip_detail_text(sip: SipAccount, open_ticket: Ticket | None = None) -> str:
    icon = STATUS_ICONS.get(sip.status, "⚪")
    status = STATUS_LABELS.get(sip.status, "Неизвестно")

    lines = [
        f"📞 <b>SIP {sip.sip_number}</b>\n",
        f"{icon} Статус: {status}",
    ]

    if sip.description:
        lines.append(f"📝 Описание: {sip.description}")
    if sip.provider:
        lines.append(f"🏢 Провайдер: {sip.provider}")
    if sip.expires_at:
        lines.append(f"📅 Действует до: {sip.expires_at.strftime('%d.%m.%Y')}")
    if sip.notes:
        lines.append(f"💬 Примечание: {sip.notes}")

    lines.append(f"\n📅 Подключён: {sip.created_at.strftime('%d.%m.%Y')}")

    if open_ticket:
        ticket_status = TICKET_STATUS_LABELS.get(open_ticket.status, open_ticket.status.value)
        lines.append(
            f"\n📋 Активная заявка: <b>#{open_ticket.id}</b> — {ticket_status}"
        )
    elif sip.status == SipStatus.active:
        lines.append("\n✅ Открытых заявок нет — можно сообщить об ошибке.")
    else:
        lines.append("\n⚠️ Сообщать об ошибках можно только по активным SIP.")

    return "\n".join(lines)


def get_sip_list_keyboard(sips: list[SipAccount]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for sip in sips:
        icon = STATUS_ICONS.get(sip.status, "⚪")
        label = f"{icon} SIP {sip.sip_number}"
        if sip.description:
            label += f" — {sip.description[:20]}"
        builder.button(text=label, callback_data=f"sip:view:{sip.id}")
    builder.button(text="🔄 Обновить", callback_data="sip:refresh")
    builder.adjust(1)
    return builder.as_markup()


def get_sip_detail_keyboard(sip_id: int, *, can_report: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if can_report:
        for preset_id in MAIN_PRESET_IDS:
            preset = GROUP_ERROR_PRESETS[preset_id]
            builder.button(
                text=preset.button,
                callback_data=f"sip:quick:{sip_id}:{preset_id}",
            )
        builder.button(
            text=OTHER_ERROR_BUTTON,
            callback_data=f"sip:report:{sip_id}",
        )
    builder.button(text="◀️ К списку", callback_data="sip:back")
    if can_report:
        builder.adjust(2, 2, 1)
    else:
        builder.adjust(1)
    return builder.as_markup()
