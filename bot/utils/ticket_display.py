from bot.catalog.group_errors import get_group_preset
from bot.keyboards.sip_menu import TICKET_STATUS_LABELS
from db.models.ticket import Ticket


def format_ticket_short(ticket: Ticket, *, sip_number: str | None = None) -> str:
    sip = sip_number or (ticket.sip.sip_number if ticket.sip else ticket.sip_number_snapshot)
    sip_part = f" · SIP <code>{sip}</code>" if sip else ""
    status = TICKET_STATUS_LABELS.get(ticket.status, ticket.status.value)
    preset = get_group_preset(ticket.error_preset_id) if ticket.error_preset_id else None
    label = preset.label if preset else ticket.description
    return f"#{ticket.id} {status}{sip_part} — {label}"
