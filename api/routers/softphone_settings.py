from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from api.rbac import get_admin_actor
from api.schemas.admin import SoftphoneTrunkBody
from bot.utils.admin_audit import log_admin_action
from core.config import settings
from db.models.user import User
from services.sip_trunk import env_trunk_defaults, get_trunk_config, save_trunk_config, trunk_is_ready

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _public_trunk_config(cfg: dict) -> dict:
    out = dict(cfg)
    out["turn_credential_set"] = bool(out.get("turn_credential"))
    out["turn_credential"] = ""
    return out


@router.get("/softphone")
async def get_softphone_settings(session: AsyncSession = Depends(get_session)):
    cfg = await get_trunk_config(session)
    env_cfg = env_trunk_defaults()
    return {
        "config": _public_trunk_config(cfg),
        "env_defaults": _public_trunk_config(env_cfg),
        "ready": trunk_is_ready(cfg),
        "env_enabled": settings.sip_trunk_enabled,
    }


@router.put("/softphone")
async def update_softphone_settings(
    body: SoftphoneTrunkBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_admin_actor),
):
    payload = body.model_dump()
    existing = await get_trunk_config(session)
    if not payload.get("turn_credential") and existing.get("turn_credential"):
        payload["turn_credential"] = existing["turn_credential"]
    if not payload.get("stun_servers"):
        payload["stun_servers"] = existing.get("stun_servers") or env_trunk_defaults()["stun_servers"]
    config = await save_trunk_config(session, payload)
    await log_admin_action(
        session, actor, "softphone_trunk_update",
        entity_type="app_setting", entity_id=0,
        new_value={k: v for k, v in config.items() if k != "turn_credential"},
    )
    return {"ok": True, "config": _public_trunk_config(config), "ready": trunk_is_ready(config)}
