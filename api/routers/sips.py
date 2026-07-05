from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from api.rbac import get_admin_actor
from api.schemas.admin import AddSipBody, SipCredentialsBody
from api.serializers import dt_iso, user_brief
from bot.utils.admin_audit import log_admin_action
from db.models.sip_account import SipStatus
from db.models.user import User
from db.repositories.sip_repo import SipRepository
from db.repositories.ticket_repo import TicketRepository
from db.repositories.user_repo import UserRepository
from services.sip_secret import encrypt_secret
from services.sip_trunk import sip_has_credentials

router = APIRouter(prefix="/api/sips", tags=["sips"])


@router.get("")
async def list_sips(
    limit: int = Query(default=100, le=200),
    offset: int = Query(default=0, ge=0),
    status: SipStatus | None = None,
    search: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    repo = SipRepository(session)
    ticket_repo = TicketRepository(session)
    sips = await repo.list_recent(limit=limit, offset=offset, status=status, search=search)
    open_counts = await ticket_repo.count_open_grouped_by_sip()
    return {
        "items": [
            {
                "id": s.id,
                "sip_number": s.sip_number,
                "description": s.description,
                "status": s.status.value,
                "user": user_brief(s.user),
                "created_at": dt_iso(s.created_at),
                "open_tickets": open_counts.get(s.id, 0),
                "has_credentials": sip_has_credentials(s),
                "auth_username": s.auth_username,
            }
            for s in sips
        ]
    }


@router.post("")
async def add_sip(
    body: AddSipBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_admin_actor),
):
    user_repo = UserRepository(session)
    sip_repo = SipRepository(session)
    target = await user_repo.get_by_telegram_id(body.telegram_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    existing = await sip_repo.get_by_number_and_user(body.sip_number, target.id)
    if existing:
        if existing.status == SipStatus.disabled:
            await sip_repo.update_status(existing, SipStatus.active)
            if body.description:
                existing.description = body.description
            if body.auth_password:
                existing.auth_secret_enc = encrypt_secret(body.auth_password)
            if body.auth_username is not None:
                existing.auth_username = body.auth_username.strip() or None
            await session.commit()
            await log_admin_action(
                session, actor, "enable_sip",
                entity_type="sip", entity_id=existing.id,
                old_value={"status": SipStatus.disabled.value},
                new_value={"status": SipStatus.active.value, "source": "web"},
            )
            return {"ok": True, "id": existing.id, "reactivated": True}
        raise HTTPException(status_code=400, detail="SIP already assigned to user")
    secret_enc = encrypt_secret(body.auth_password) if body.auth_password else None
    sip = await sip_repo.create(
        user_id=target.id,
        sip_number=body.sip_number.strip(),
        description=body.description,
        added_by=actor.id,
        auth_username=body.auth_username,
        auth_secret_enc=secret_enc,
    )
    await log_admin_action(
        session, actor, "add_sip",
        entity_type="sip", entity_id=sip.id,
        new_value={"sip_number": sip.sip_number, "user_id": target.id, "source": "web"},
    )
    return {"ok": True, "id": sip.id}


@router.post("/{sip_id}/disable")
async def disable_sip(
    sip_id: int,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_admin_actor),
):
    repo = SipRepository(session)
    sip = await repo.get_by_id(sip_id)
    if not sip:
        raise HTTPException(status_code=404, detail="SIP not found")
    await repo.update_status(sip, SipStatus.disabled)
    await log_admin_action(
        session, actor, "remove_sip",
        entity_type="sip", entity_id=sip.id,
        new_value={"status": SipStatus.disabled.value, "source": "web"},
    )
    return {"ok": True}


@router.post("/{sip_id}/enable")
async def enable_sip(
    sip_id: int,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_admin_actor),
):
    repo = SipRepository(session)
    sip = await repo.get_by_id(sip_id)
    if not sip:
        raise HTTPException(status_code=404, detail="SIP not found")
    if sip.status == SipStatus.active:
        raise HTTPException(status_code=400, detail="SIP is already active")
    if sip.status == SipStatus.frozen:
        raise HTTPException(status_code=400, detail="SIP is frozen — unfreeze via support first")
    old_status = sip.status.value
    await repo.update_status(sip, SipStatus.active)
    await log_admin_action(
        session, actor, "enable_sip",
        entity_type="sip", entity_id=sip.id,
        old_value={"status": old_status},
        new_value={"status": SipStatus.active.value, "source": "web"},
    )
    return {"ok": True, "status": SipStatus.active.value}


@router.patch("/{sip_id}/credentials")
async def update_sip_credentials(
    sip_id: int,
    body: SipCredentialsBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_admin_actor),
):
    repo = SipRepository(session)
    sip = await repo.get_by_id(sip_id)
    if not sip:
        raise HTTPException(status_code=404, detail="SIP not found")
    if not body.auth_password and body.auth_username is None:
        raise HTTPException(status_code=400, detail="Nothing to update")
    secret_enc = encrypt_secret(body.auth_password) if body.auth_password else sip.auth_secret_enc
    if body.auth_password is None and not sip.auth_secret_enc:
        raise HTTPException(status_code=400, detail="auth_password required for new credentials")
    username = body.auth_username if body.auth_username is not None else sip.auth_username
    await repo.set_credentials(sip, auth_username=username, auth_secret_enc=secret_enc)
    await log_admin_action(
        session, actor, "sip_credentials_update",
        entity_type="sip", entity_id=sip.id,
        new_value={"auth_username": username, "source": "web"},
    )
    return {"ok": True, "has_credentials": sip_has_credentials(sip), "auth_username": sip.auth_username}
