from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from api.rbac import get_admin_actor
from api.schemas.admin import NotificationSettingsBody
from bot.utils.admin_audit import log_admin_action
from core.notification_config import env_defaults, get_notification_config, save_notification_config
from db.models.user import User

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/notifications")
async def get_notifications_settings(session: AsyncSession = Depends(get_session)):
    config = await get_notification_config(session)
    return {
        "config": config,
        "env_defaults": env_defaults(),
        "event_labels": {
            "ticket_new": "Новая заявка",
            "ticket_status": "Изменение статуса",
            "ticket_resolved": "Заявка решена",
            "group_pending": "Новая группа на одобрение",
            "deposit_new": "Заявка на пополнение USDT",
        },
    }


@router.put("/notifications")
async def update_notifications_settings(
    body: NotificationSettingsBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_admin_actor),
):
    payload = body.model_dump()
    config = await save_notification_config(session, payload)
    await log_admin_action(
        session, actor, "notification_settings_update",
        entity_type="app_setting", entity_id=0,
        new_value=config,
    )
    return {"ok": True, "config": config}
