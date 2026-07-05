"""Mini App SIP softphone API (WebRTC via JsSIP)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_redis, get_session
from api.deps_mini import get_mini_user
from api.services.mini_app import build_softphone_summary
from db.models.sip_call_log import SipCallLog
from db.models.user import User
from db.repositories.sip_repo import SipRepository
from services.sip_trunk import build_webrtc_session, get_trunk_config, trunk_is_ready

router = APIRouter(prefix="/api/mini/softphone", tags=["mini-softphone"])

SESSION_RATE_LIMIT = 12
SESSION_RATE_WINDOW = 60


class SoftphoneCallEventBody(BaseModel):
    sip_id: int
    direction: str = Field(pattern=r"^(inbound|outbound)$")
    remote_number: str = Field(min_length=1, max_length=64)
    status: str = Field(min_length=1, max_length=32)
    duration_ms: int | None = Field(default=None, ge=0, le=86_400_000)
    started_at: datetime | None = None
    ended_at: datetime | None = None


async def _rate_limit_session(redis: Redis, user_id: int) -> None:
    key = f"softphone:session:{user_id}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, SESSION_RATE_WINDOW)
    if count > SESSION_RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many softphone session requests")


@router.get("/status")
async def softphone_status(
    user: User = Depends(get_mini_user),
    session: AsyncSession = Depends(get_session),
):
    return await build_softphone_summary(session, user.id)


@router.get("/session/{sip_id}")
async def softphone_session(
    sip_id: int,
    user: User = Depends(get_mini_user),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
):
    await _rate_limit_session(redis, user.id)
    cfg = await get_trunk_config(session)
    if not trunk_is_ready(cfg):
        raise HTTPException(status_code=503, detail="SIP trunk is not configured")

    sip_repo = SipRepository(session)
    sip = await sip_repo.get_by_id(sip_id)
    if not sip or sip.user_id != user.id:
        raise HTTPException(status_code=404, detail="SIP not found")
    try:
        payload = build_webrtc_session(sip, cfg)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return payload


@router.post("/events")
async def softphone_call_event(
    body: SoftphoneCallEventBody,
    user: User = Depends(get_mini_user),
    session: AsyncSession = Depends(get_session),
):
    sip_repo = SipRepository(session)
    sip = await sip_repo.get_by_id(body.sip_id)
    if not sip or sip.user_id != user.id:
        raise HTTPException(status_code=404, detail="SIP not found")

    log = SipCallLog(
        user_id=user.id,
        sip_id=sip.id,
        direction=body.direction,
        remote_number=body.remote_number.strip(),
        status=body.status.strip(),
        duration_ms=body.duration_ms,
        started_at=body.started_at or datetime.now(timezone.utc),
        ended_at=body.ended_at,
    )
    session.add(log)
    await session.commit()
    return {"ok": True, "id": log.id}
