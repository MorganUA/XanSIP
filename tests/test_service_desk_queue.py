"""Тесты очереди колл-центра."""

from datetime import datetime, timedelta, timezone

from api.services.service_desk_queue import (
    SLA_BREACH_SECONDS,
    build_queue_summary,
    is_sla_breach,
    sort_service_desk_queue,
    ticket_age_seconds,
)
from db.models.ticket import ErrorType, Ticket, TicketSource, TicketStatus


def _ticket(
    ticket_id: int,
    status: TicketStatus,
    *,
    minutes_ago: int = 0,
) -> Ticket:
    created = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return Ticket(
        id=ticket_id,
        user_id=1,
        error_type=ErrorType.other,
        description="test",
        status=status,
        source=TicketSource.group_chat,
        created_at=created,
    )


def _ticket_at(
    ticket_id: int,
    status: TicketStatus,
    created_at: datetime,
) -> Ticket:
    return Ticket(
        id=ticket_id,
        user_id=1,
        error_type=ErrorType.other,
        description="test",
        status=status,
        source=TicketSource.group_chat,
        created_at=created_at,
    )


def test_sort_new_before_in_progress_fifo():
    tickets = [
        _ticket(2, TicketStatus.in_progress, minutes_ago=10),
        _ticket(1, TicketStatus.new, minutes_ago=5),
        _ticket(3, TicketStatus.new, minutes_ago=1),
    ]
    ordered = sort_service_desk_queue(tickets)
    assert [t.id for t in ordered] == [1, 3, 2]


def test_sla_breach_after_threshold():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    created = now - timedelta(seconds=SLA_BREACH_SECONDS + 1)
    assert is_sla_breach(created, now=now)
    assert ticket_age_seconds(created, now=now) > SLA_BREACH_SECONDS


def test_queue_summary_counts():
    now = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    tickets = [
        _ticket_at(1, TicketStatus.new, now - timedelta(minutes=2)),
        _ticket_at(2, TicketStatus.new, now - timedelta(minutes=10)),
        _ticket_at(3, TicketStatus.in_progress, now - timedelta(minutes=2)),
    ]
    summary = build_queue_summary(tickets, now=now)
    assert summary["total"] == 3
    assert summary["new"] == 2
    assert summary["in_progress"] == 1
    assert summary["sla_breach"] == 1
