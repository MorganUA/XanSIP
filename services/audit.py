"""Неизменяемый журнал событий системы."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import User
from db.repositories.audit_repo import AuditRepository


async def log_audit(
    session: AsyncSession,
    *,
    category: str,
    action: str,
    actor: User | None = None,
    actor_label: str | None = None,
    entity_type: str | None = None,
    entity_id: str | int | None = None,
    details: dict | None = None,
) -> None:
    repo = AuditRepository(session)
    label = actor_label
    if actor and not label:
        label = actor.internal_id or str(actor.telegram_id)
    await repo.append(
        category=category,
        action=action,
        actor_user_id=actor.id if actor else None,
        actor_label=label,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
