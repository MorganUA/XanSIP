"""Shared Mini App payload builders."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.group_errors import GROUP_ERROR_PRESETS, MAIN_PRESET_IDS, SUBMENU_PRESET_IDS
from db.models.user import User, UserRole
from db.repositories.sip_repo import SipRepository
from db.repositories.ticket_repo import TicketRepository
from services.sip_trunk import get_trunk_config, sip_has_credentials, trunk_is_ready


def _preset_items(preset_ids: tuple[str, ...] | list[str]) -> list[dict[str, str]]:
    return [
        {
            "id": pid,
            "button": GROUP_ERROR_PRESETS[pid].button,
            "label": GROUP_ERROR_PRESETS[pid].label,
        }
        for pid in preset_ids
    ]


def serialize_mini_user(user: User) -> dict:
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "internal_id": user.internal_id,
        "first_name": user.first_name,
        "username": user.username,
        "role": user.role.value,
    }


async def load_user_sip_items(session: AsyncSession, user_id: int) -> list[dict]:
    sip_repo = SipRepository(session)
    ticket_repo = TicketRepository(session)
    sips = await sip_repo.get_active_by_user_id(user_id)
    open_by_sip = await ticket_repo.first_open_ticket_id_by_sip_ids([s.id for s in sips])
    return [
        {
            "id": sip.id,
            "sip_number": sip.sip_number,
            "description": sip.description,
            "status": sip.status.value,
            "open_ticket_id": open_by_sip.get(sip.id),
        }
        for sip in sips
    ]


async def build_softphone_summary(session: AsyncSession, user_id: int) -> dict:
    cfg = await get_trunk_config(session)
    ready = trunk_is_ready(cfg)
    sip_repo = SipRepository(session)
    sips = await sip_repo.get_active_by_user_id(user_id)
    return {
        "enabled": ready,
        "trunk": {
            "display_name": cfg.get("display_name"),
            "sip_domain": cfg.get("sip_domain") if ready else None,
        },
        "lines": [
            {
                "id": s.id,
                "sip_number": s.sip_number,
                "description": s.description,
                "has_credentials": sip_has_credentials(s),
                "callable": sip_has_credentials(s) and ready,
            }
            for s in sips
        ],
    }


async def build_mini_bootstrap(session: AsyncSession, user: User) -> dict:
    ticket_repo = TicketRepository(session)
    sips = await load_user_sip_items(session, user.id)
    open_tickets = await ticket_repo.count_active_by_user(user.id)
    softphone = await build_softphone_summary(session, user.id)
    return {
        "user": serialize_mini_user(user),
        "sips_count": len(sips),
        "open_tickets": open_tickets,
        "quick_presets": _preset_items(MAIN_PRESET_IDS),
        "extra_presets": _preset_items(SUBMENU_PRESET_IDS),
        "is_staff": user.role in (UserRole.support, UserRole.admin, UserRole.superadmin),
        "sips": sips,
        "softphone": softphone,
    }
