from sqlalchemy.ext.asyncio import AsyncSession

from services.audit import log_audit
from db.models.user import User


async def log_admin_action(
    session: AsyncSession,
    actor: User,
    action: str,
    *,
    entity_type: str | None = None,
    entity_id: int | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
    extra: dict | None = None,
) -> None:
    """Пишет только в audit_events (admin_logs deprecated)."""
    await log_audit(
        session,
        category="admin",
        action=action,
        actor=actor,
        entity_type=entity_type,
        entity_id=entity_id,
        details={"old": old_value, "new": new_value, "extra": extra},
    )
