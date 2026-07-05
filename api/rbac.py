"""Web CRM role checks — support vs admin vs superadmin."""

from __future__ import annotations

from fastapi import Depends, HTTPException

from api.deps import get_web_actor
from db.models.user import User, UserRole


def require_admin(actor: User) -> None:
    if actor.role not in (UserRole.admin, UserRole.superadmin):
        raise HTTPException(status_code=403, detail="Admin role required")


def require_superadmin(actor: User) -> None:
    if actor.role != UserRole.superadmin:
        raise HTTPException(status_code=403, detail="Superadmin role required")


async def get_admin_actor(actor: User = Depends(get_web_actor)) -> User:
    require_admin(actor)
    return actor
