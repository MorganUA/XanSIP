"""Unit tests: ticket status transition matrix."""
from db.models.ticket import TicketStatus
from bot.utils.ticket_status import can_transition, transition_error, ALLOWED_TRANSITIONS


def test_idempotent_same_status():
    for status in TicketStatus:
        assert can_transition(status, status) is True


def test_new_to_resolved_allowed():
    assert can_transition(TicketStatus.new, TicketStatus.resolved) is True


def test_resolved_to_closed_allowed():
    assert can_transition(TicketStatus.resolved, TicketStatus.closed) is True


def test_closed_to_resolved_blocked():
    assert can_transition(TicketStatus.closed, TicketStatus.resolved) is False
    assert "невозможен" in transition_error(TicketStatus.closed, TicketStatus.resolved)


def test_rejected_terminal():
    assert can_transition(TicketStatus.rejected, TicketStatus.in_progress) is False
    assert ALLOWED_TRANSITIONS[TicketStatus.rejected] == set()


def test_waiting_info_to_in_progress():
    assert can_transition(TicketStatus.waiting_info, TicketStatus.in_progress) is True


def test_all_allowed_edges():
    for current, targets in ALLOWED_TRANSITIONS.items():
        for target in targets:
            assert can_transition(current, target) is True
