"""Сериализация заявок и подписи для Web CRM / API."""

from __future__ import annotations

from api.services.service_desk_queue import SLA_BREACH_SECONDS, ticket_age_seconds
from bot.catalog.error_labels import ERROR_TYPE_LABELS
from bot.catalog.errors import get_preset_label
from bot.catalog.group_errors import get_group_preset
from db.models.ticket import ErrorType, Ticket, TicketSource, TicketStatus
from db.models.user import User

SOURCE_LABELS = {
    TicketSource.personal_chat: "Личный чат",
    TicketSource.group_chat: "Группа (колл-центр)",
    TicketSource.command: "Команда /err",
}

STATUS_LABELS = {
    TicketStatus.new: "Новая",
    TicketStatus.in_progress: "В работе",
    TicketStatus.waiting_info: "Ожидание инфо",
    TicketStatus.resolved: "Решена",
    TicketStatus.rejected: "Отклонена",
    TicketStatus.closed: "Закрыта",
}

OPEN_STATUSES = (
    TicketStatus.new,
    TicketStatus.in_progress,
    TicketStatus.waiting_info,
)


def resolve_error_label(
    preset_id: str | None,
    error_type: ErrorType,
    description: str,
) -> str:
    if preset_id:
        group_preset = get_group_preset(preset_id)
        if group_preset:
            return group_preset.label
        personal = get_preset_label(preset_id, description)
        if personal and personal != description:
            return personal
    return ERROR_TYPE_LABELS.get(error_type, error_type.value)


def ticket_sip_number(ticket: Ticket) -> str | None:
    if ticket.sip_number_snapshot:
        return ticket.sip_number_snapshot
    if ticket.sip:
        return ticket.sip.sip_number
    return None


def enrich_ticket_queue_fields(
    data: dict,
    *,
    created_at,
    assignee: User | None = None,
) -> dict:
    age = ticket_age_seconds(created_at)
    data["age_seconds"] = age
    data["sla_breach"] = age > SLA_BREACH_SECONDS
    data["sla_seconds"] = SLA_BREACH_SECONDS
    data["assigned_to"] = _user_brief(assignee) if assignee else None
    return data


def serialize_ticket_brief(ticket: Ticket, *, assignee: User | None = None) -> dict:
    data = {
        "id": ticket.id,
        "status": ticket.status.value,
        "status_label": STATUS_LABELS.get(ticket.status, ticket.status.value),
        "error_type": ticket.error_type.value,
        "error_preset_id": ticket.error_preset_id,
        "error_label": resolve_error_label(
            ticket.error_preset_id, ticket.error_type, ticket.description,
        ),
        "description": ticket.description,
        "source": ticket.source.value,
        "source_label": SOURCE_LABELS.get(ticket.source, ticket.source.value),
        "sip_number": ticket_sip_number(ticket),
        "initiator_telegram_id": ticket.initiator_telegram_id,
        "user": _user_brief(ticket.user) if ticket.user else None,
        "created_at": _iso(ticket.created_at),
        "is_service_desk": ticket.source == TicketSource.group_chat,
        "is_open": ticket.status in OPEN_STATUSES,
    }
    return enrich_ticket_queue_fields(
        data, created_at=ticket.created_at, assignee=assignee,
    )


def _status_label(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return STATUS_LABELS.get(TicketStatus(value), value)
    except ValueError:
        return value


def serialize_ticket_history(ticket: Ticket) -> list[dict]:
    rows = sorted(ticket.status_history, key=lambda h: h.created_at)
    return [
        {
            "old_status": h.old_status,
            "old_status_label": _status_label(h.old_status),
            "new_status": h.new_status,
            "new_status_label": _status_label(h.new_status),
            "comment": h.comment,
            "created_at": _iso(h.created_at),
        }
        for h in rows
    ]


def serialize_ticket_detail(
    ticket: Ticket,
    *,
    group_name: str | None = None,
    group_chat_id: int | None = None,
    assignee: User | None = None,
) -> dict:
    data = serialize_ticket_brief(ticket, assignee=assignee)
    data.update({
        "group_name": group_name,
        "group_chat_id": group_chat_id,
        "updated_at": _iso(ticket.updated_at),
        "resolved_at": _iso(ticket.resolved_at),
        "history": serialize_ticket_history(ticket),
    })
    return data


def _user_brief(user: User | None) -> dict | None:
    if not user:
        return None
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "internal_id": user.internal_id,
        "username": user.username,
        "first_name": user.first_name,
        "role": user.role.value,
    }


def _iso(value) -> str | None:
    return value.isoformat() if value else None
