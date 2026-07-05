from fastapi import APIRouter, Depends, HTTPException, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_redis, get_session, get_web_actor
from api.deps_bot import verify_bot_secret
from api.schemas.admin import CreateTicketBody, TicketStatusBody
from api.services.bot_webhook import notify_ticket_status_changed
from api.services.service_desk import ServiceDeskError, create_group_service_desk_ticket
from api.services.service_desk_queue import build_queue_summary, sort_service_desk_queue
from api.services.ticket_present import serialize_ticket_brief, serialize_ticket_detail
from bot.utils.admin_audit import log_admin_action
from bot.utils.ticket_status import can_transition, transition_error
from db.models.ticket import TicketStatus
from db.models.user import User
from db.repositories.group_repo import GroupRepository
from db.repositories.ticket_repo import TicketRepository
from db.repositories.user_repo import UserRepository

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.get("")
async def list_tickets(
    status: TicketStatus | None = None,
    limit: int = Query(default=100, le=200),
    session: AsyncSession = Depends(get_session),
):
    repo = TicketRepository(session)
    tickets = await repo.list_recent(limit=limit, status=status)
    return {"items": [serialize_ticket_brief(t) for t in tickets]}


@router.get("/service-desk")
async def list_service_desk_tickets(session: AsyncSession = Depends(get_session)):
    repo = TicketRepository(session)
    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    tickets = sort_service_desk_queue(await repo.list_active_service_desk())
    assignee_ids = [t.assigned_to for t in tickets if t.assigned_to]
    assignees = await user_repo.get_by_ids(assignee_ids)
    group_ids = {t.group_id for t in tickets if t.group_id}
    groups_by_id: dict[int, object] = {}
    for gid in group_ids:
        g = await group_repo.get_by_id(gid)
        if g:
            groups_by_id[gid] = g
    items = []
    for t in tickets:
        group_name = None
        group_chat_id = None
        if t.group_id and t.group_id in groups_by_id:
            g = groups_by_id[t.group_id]
            group_name = g.group_name
            group_chat_id = g.telegram_group_id
        brief = serialize_ticket_brief(t, assignee=assignees.get(t.assigned_to))
        brief["group_name"] = group_name
        brief["group_chat_id"] = group_chat_id
        items.append(brief)
    return {"items": items, "summary": build_queue_summary(tickets)}


@router.get("/{ticket_id}")
async def get_ticket_detail(ticket_id: int, session: AsyncSession = Depends(get_session)):
    repo = TicketRepository(session)
    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    ticket = await repo.get_with_details(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    group_name = None
    group_chat_id = None
    if ticket.group_id:
        group = await group_repo.get_by_id(ticket.group_id)
        if group:
            group_name = group.group_name
            group_chat_id = group.telegram_group_id

    assignee = None
    if ticket.assigned_to:
        assignee = await user_repo.get_by_id(ticket.assigned_to)

    return serialize_ticket_detail(
        ticket,
        group_name=group_name,
        group_chat_id=group_chat_id,
        assignee=assignee,
    )


@router.post("/{ticket_id}/take")
async def take_ticket(
    ticket_id: int,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_web_actor),
):
    repo = TicketRepository(session)
    ticket = await repo.get_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.status == TicketStatus.in_progress:
        return {"ok": True, "status": TicketStatus.in_progress.value, "noop": True}
    if not can_transition(ticket.status, TicketStatus.in_progress):
        raise HTTPException(
            status_code=400,
            detail=transition_error(ticket.status, TicketStatus.in_progress) or "Cannot take ticket",
        )
    old_status = ticket.status.value
    await repo.assign(ticket, actor.id)
    await repo.update_status(
        ticket, TicketStatus.in_progress,
        changed_by_id=actor.id,
        comment="Взято в работу (Web CRM)",
    )
    await log_admin_action(
        session, actor, "take_ticket",
        entity_type="ticket", entity_id=ticket.id,
        new_value={"status": TicketStatus.in_progress.value, "source": "web"},
    )
    await notify_ticket_status_changed(
        ticket_id=ticket.id,
        old_status=old_status,
        new_status=TicketStatus.in_progress.value,
        comment="Взято в работу (Web CRM)",
    )
    return {"ok": True, "status": TicketStatus.in_progress.value}


@router.post("/create")
async def create_ticket_from_bot(
    body: CreateTicketBody,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    _: None = Depends(verify_bot_secret),
):
    try:
        result = await create_group_service_desk_ticket(
            session,
            redis,
            sip_number=body.sip_number,
            error_preset_id=body.error_preset_id,
            initiator_telegram_id=body.initiator_telegram_id,
            group_chat_id=body.group_chat_id,
        )
    except ServiceDeskError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return result


@router.post("/{ticket_id}/status")
async def update_ticket_status(
    ticket_id: int,
    body: TicketStatusBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_web_actor),
):
    repo = TicketRepository(session)
    ticket = await repo.get_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.status == body.status:
        return {"ok": True, "status": body.status.value, "noop": True}

    if not can_transition(ticket.status, body.status):
        raise HTTPException(
            status_code=400,
            detail=transition_error(ticket.status, body.status) or (
                f"Transition {ticket.status.value} → {body.status.value} not allowed"
            ),
        )
    old_status = ticket.status.value
    await repo.update_status(ticket, body.status, changed_by_id=actor.id, comment=body.comment)
    await log_admin_action(
        session, actor, "ticket_status",
        entity_type="ticket", entity_id=ticket.id,
        old_value={"status": old_status},
        new_value={"status": body.status.value, "source": "web"},
    )

    notified = await notify_ticket_status_changed(
        ticket_id=ticket.id,
        old_status=old_status,
        new_status=body.status.value,
        comment=body.comment,
    )

    return {"ok": True, "status": body.status.value, "notified": notified}
