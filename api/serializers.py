from datetime import datetime

from db.models.user import User


def dt_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def user_brief(user: User | None) -> dict | None:
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


def user_full(user: User) -> dict:
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "internal_id": user.internal_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role.value,
        "is_banned": user.is_banned,
        "ban_reason": user.ban_reason,
        "created_at": dt_iso(user.created_at),
    }
