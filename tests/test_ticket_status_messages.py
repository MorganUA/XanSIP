from db.models.ticket import TicketStatus
from bot.utils.ticket_status_messages import (
    build_ticket_status_message,
    ticket_status_notify_event,
)


def test_resolved_message():
    text = build_ticket_status_message(5, TicketStatus.resolved)
    assert "#5" in text
    assert "решена" in text.lower()


def test_notify_event_resolved():
    assert ticket_status_notify_event(TicketStatus.resolved) == "ticket_resolved"
    assert ticket_status_notify_event(TicketStatus.in_progress) == "ticket_status"
