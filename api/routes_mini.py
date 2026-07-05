"""Mini App API routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_redis, get_session
from api.deps_mini import get_mini_user
from api.services.mini_app import (
    _preset_items,
    build_mini_bootstrap,
    build_softphone_summary,
    load_user_sip_items,
)
from api.services.ticket_present import serialize_ticket_brief, STATUS_LABELS
from api.services.user_ticket_create import create_personal_ticket
from bot.catalog.group_errors import MAIN_PRESET_IDS, SUBMENU_PRESET_IDS
from db.models.user import User
from db.repositories.ticket_repo import TicketRepository

router = APIRouter(prefix="/api/mini", tags=["mini"])


class MiniTicketBody(BaseModel):
    sip_id: int
    preset_id: str = Field(min_length=1, max_length=50)


@router.get("/bootstrap")
async def mini_bootstrap(
    user: User = Depends(get_mini_user),
    session: AsyncSession = Depends(get_session),
):
    """Single round-trip payload for Mini App cold start."""
    return await build_mini_bootstrap(session, user)


@router.get("/dashboard")
async def mini_dashboard(
    user: User = Depends(get_mini_user),
    session: AsyncSession = Depends(get_session),
):
    ticket_repo = TicketRepository(session)
    sips = await load_user_sip_items(session, user.id)
    from api.services.mini_app import serialize_mini_user

    return {
        "user": serialize_mini_user(user),
        "sips_count": len(sips),
        "open_tickets": await ticket_repo.count_active_by_user(user.id),
        "quick_presets": _preset_items(MAIN_PRESET_IDS),
        "is_staff": user.role.value in ("support", "admin", "superadmin"),
    }


@router.get("/sips")
async def mini_sips(
    user: User = Depends(get_mini_user),
    session: AsyncSession = Depends(get_session),
):
    items = await load_user_sip_items(session, user.id)
    return {"items": items}


@router.get("/tickets")
async def mini_tickets(
    user: User = Depends(get_mini_user),
    session: AsyncSession = Depends(get_session),
):
    ticket_repo = TicketRepository(session)
    tickets = await ticket_repo.get_by_user_id(user.id, limit=30)
    items = []
    for t in tickets:
        brief = serialize_ticket_brief(t)
        brief["status_label"] = STATUS_LABELS.get(t.status, t.status.value)
        items.append(brief)
    return {"items": items}


@router.get("/presets")
async def mini_presets(user: User = Depends(get_mini_user)):
    _ = user
    return {
        "main": _preset_items(MAIN_PRESET_IDS),
        "extra": _preset_items(SUBMENU_PRESET_IDS),
    }


@router.post("/tickets")
async def mini_create_ticket(
    body: MiniTicketBody,
    user: User = Depends(get_mini_user),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
):
    try:
        result = await create_personal_ticket(
            session, redis, user=user, sip_id=body.sip_id, preset_id=body.preset_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **result}
