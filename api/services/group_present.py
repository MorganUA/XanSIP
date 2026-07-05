"""Сериализация групп / колл-центров для Web CRM."""

from __future__ import annotations

from db.models.group import Group
from db.models.user import User


def group_status_key(group: Group) -> str:
    if group.is_deleted:
        return "deleted"
    if group.is_banned:
        return "banned"
    if group.is_frozen:
        return "frozen"
    if not group.is_approved:
        return "pending"
    return "active"


GROUP_STATUS_LABELS = {
    "active": "Активна",
    "pending": "Ожидает",
    "frozen": "Заморожена",
    "banned": "Бан",
    "deleted": "Удалена",
}


def serialize_group(
    group: Group,
    *,
    owner: User | None = None,
    approved_by: User | None = None,
    open_tickets: int = 0,
) -> dict:
    status = group_status_key(group)
    return {
        "id": group.id,
        "telegram_group_id": group.telegram_group_id,
        "group_name": group.group_name,
        "call_center_label": group.call_center_label,
        "display_name": group.call_center_label or group.group_name or f"Группа #{group.id}",
        "tariff": group.tariff,
        "tariff_notes": group.tariff_notes,
        "work_conditions": group.work_conditions,
        "participants_info": group.participants_info,
        "contact_info": group.contact_info,
        "notes": group.notes,
        "is_approved": group.is_approved,
        "is_banned": group.is_banned,
        "ban_reason": group.ban_reason,
        "is_frozen": group.is_frozen,
        "frozen_reason": group.frozen_reason,
        "frozen_at": _iso(group.frozen_at),
        "is_deleted": group.is_deleted,
        "deleted_at": _iso(group.deleted_at),
        "status": status,
        "status_label": GROUP_STATUS_LABELS.get(status, status),
        "owner": _user_brief(owner),
        "approved_by": _user_brief(approved_by),
        "approved_at": _iso(group.approved_at),
        "open_tickets": open_tickets,
        "created_at": _iso(group.created_at),
    }


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
