from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from api.services.sip_stats import build_sip_work_report, report_to_csv
from api.services.ticket_present import OPEN_STATUSES
from core.config import settings
from db.repositories.group_repo import GroupRepository
from db.repositories.sip_repo import SipRepository
from db.repositories.ticket_repo import TicketRepository
from db.repositories.user_repo import UserRepository

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
async def dashboard(session: AsyncSession = Depends(get_session)):
    user_repo = UserRepository(session)
    ticket_repo = TicketRepository(session)
    group_repo = GroupRepository(session)
    sip_repo = SipRepository(session)

    ticket_counts = await ticket_repo.count_by_status()
    sip_counts = await sip_repo.count_by_status()
    groups = await group_repo.get_all()
    pending_groups = sum(
        1 for g in groups if not g.is_approved and not g.is_banned and not g.is_frozen
    )
    groups_active = sum(
        1 for g in groups if g.is_approved and not g.is_banned and not g.is_frozen
    )
    groups_frozen = sum(1 for g in groups if g.is_frozen and not g.is_banned)
    service_desk_active = len(await ticket_repo.list_active_service_desk(limit=500))
    sd_tickets = await ticket_repo.list_active_service_desk(limit=500)
    now = datetime.now(timezone.utc)
    sla_breach = 0
    for t in sd_tickets:
        created = t.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if (now - created).total_seconds() > 180:
            sla_breach += 1

    tickets_open = sum(ticket_counts.get(s.value, 0) for s in OPEN_STATUSES)

    return {
        "users_total": await user_repo.count_all(),
        "tickets_open": tickets_open,
        "tickets_new": ticket_counts.get("new", 0),
        "tickets_in_progress": ticket_counts.get("in_progress", 0),
        "tickets_waiting_info": ticket_counts.get("waiting_info", 0),
        "service_desk_active": service_desk_active,
        "sla_breach": sla_breach,
        "tickets_by_status": ticket_counts,
        "sips_total": sum(sip_counts.values()),
        "sips_active": sip_counts.get("active", 0),
        "sips_disabled": sip_counts.get("disabled", 0),
        "groups_total": len(groups),
        "groups_pending": pending_groups,
        "groups_active": groups_active,
        "groups_frozen": groups_frozen,
        "test_mode": settings.test_mode,
    }


@router.get("/stats/sip-work")
async def sip_work_stats(
    days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
):
    return await build_sip_work_report(session, days=days)


@router.get("/stats/sip-work/export")
async def sip_work_stats_export(
    days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
):
    report = await build_sip_work_report(session, days=days)
    csv_text = report_to_csv(report)
    filename = f"sipcrm-report-{days}d.csv"
    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
