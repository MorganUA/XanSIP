from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from api.rbac import get_admin_actor
from api.schemas.admin import BanBody, RoleBody
from api.serializers import user_full
from bot.utils.admin_audit import log_admin_action
from db.models.user import User, UserRole
from db.repositories.user_repo import UserRepository

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
async def list_users(
    search: str | None = None,
    limit: int = Query(default=100, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    repo = UserRepository(session)
    users = await repo.list_recent(limit=limit, offset=offset, search=search)
    return {"items": [user_full(u) for u in users]}


@router.post("/{user_id}/ban")
async def ban_user(
    user_id: int,
    body: BanBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_admin_actor),
):
    repo = UserRepository(session)
    target = await repo.get_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.role in (UserRole.admin, UserRole.superadmin):
        raise HTTPException(status_code=400, detail="Cannot ban administrator")
    await repo.ban(target, body.reason, banned_by_id=actor.id)
    await log_admin_action(
        session, actor, "ban_user",
        entity_type="user", entity_id=target.id,
        new_value={"telegram_id": target.telegram_id, "reason": body.reason, "source": "web"},
    )
    return {"ok": True}


@router.post("/{user_id}/unban")
async def unban_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_admin_actor),
):
    repo = UserRepository(session)
    target = await repo.get_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    await repo.unban(target)
    await log_admin_action(
        session, actor, "unban_user",
        entity_type="user", entity_id=target.id,
        new_value={"telegram_id": target.telegram_id, "source": "web"},
    )
    return {"ok": True}


@router.post("/{user_id}/role")
async def set_role(
    user_id: int,
    body: RoleBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_admin_actor),
):
    repo = UserRepository(session)
    target = await repo.get_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == actor.id:
        raise HTTPException(status_code=400, detail="Cannot change own role")
    if body.role in (UserRole.admin, UserRole.superadmin) and actor.role != UserRole.superadmin:
        raise HTTPException(status_code=403, detail="Only superadmin can assign admin roles")
    old_role = target.role.value
    target.role = body.role
    await session.commit()
    await log_admin_action(
        session, actor, "set_role",
        entity_type="user", entity_id=target.id,
        old_value={"role": old_role},
        new_value={"role": body.role.value, "source": "web"},
    )
    return {"ok": True, "role": body.role.value}
