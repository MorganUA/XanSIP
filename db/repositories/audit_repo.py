from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.audit_event import AuditEvent


class AuditRepository:
    """Только добавление и чтение — без update/delete."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def append(
        self,
        *,
        category: str,
        action: str,
        actor_user_id: int | None = None,
        actor_label: str | None = None,
        entity_type: str | None = None,
        entity_id: str | int | None = None,
        details: dict | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            actor_user_id=actor_user_id,
            actor_label=actor_label,
            category=category,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=details,
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def list_events(
        self,
        *,
        category: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[AuditEvent]:
        q = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit).offset(offset)
        if category:
            q = q.where(AuditEvent.category == category)
        return list((await self.session.execute(q)).scalars().all())
