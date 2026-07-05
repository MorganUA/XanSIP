"""Проверки доступа группы колл-центра (без зависимости от aiogram)."""

from __future__ import annotations

from db.models.group import Group


def group_access_error(group: Group | None) -> str | None:
    if not group or not group.is_approved:
        return "⛔ Эта группа не авторизована. Дождитесь одобрения администратором."
    if group.is_deleted:
        return "🗑 Колл-центр этой группы отключён."
    if group.is_banned:
        return "🚫 Эта группа заблокирована."
    if group.is_frozen:
        reason = group.frozen_reason or "не указана"
        return (
            f"⏸ Колл-центр временно заморожен.\nПричина: {reason}\n\n"
            "Создание заявок /err недоступно."
        )
    return None
