"""Очередь колл-центра: сортировка, SLA, сводка."""

from __future__ import annotations

from datetime import datetime, timezone

from db.models.ticket import Ticket, TicketStatus

SLA_BREACH_SECONDS = 180

QUEUE_STATUS_ORDER = {
    TicketStatus.new: 0,
    TicketStatus.in_progress: 1,
    TicketStatus.waiting_info: 2,
}


def ticket_age_seconds(created_at: datetime, *, now: datetime | None = None) -> int:
    ref = now or datetime.now(timezone.utc)
    created = created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return max(0, int((ref - created).total_seconds()))


def is_sla_breach(created_at: datetime, *, now: datetime | None = None) -> bool:
    return ticket_age_seconds(created_at, now=now) > SLA_BREACH_SECONDS


def sort_service_desk_queue(tickets: list[Ticket]) -> list[Ticket]:
    """Приоритет: новые → в работе → ожидание; внутри группы — старейшие первыми (FIFO)."""
    return sorted(
        tickets,
        key=lambda t: (
            QUEUE_STATUS_ORDER.get(t.status, 99),
            t.created_at,
        ),
    )


def build_queue_summary(tickets: list[Ticket], *, now: datetime | None = None) -> dict:
    ref = now or datetime.now(timezone.utc)
    counts = {s.value: 0 for s in QUEUE_STATUS_ORDER}
    sla_breach = 0
    for t in tickets:
        counts[t.status.value] = counts.get(t.status.value, 0) + 1
        if is_sla_breach(t.created_at, now=ref):
            sla_breach += 1
    return {
        "total": len(tickets),
        "new": counts.get("new", 0),
        "in_progress": counts.get("in_progress", 0),
        "waiting_info": counts.get("waiting_info", 0),
        "sla_breach": sla_breach,
        "sla_seconds": SLA_BREACH_SECONDS,
    }
