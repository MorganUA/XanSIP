from db.models.ticket import TicketStatus

# Активные заявки (для фильтров очереди)
ACTIVE_STATUSES = {
    TicketStatus.new,
    TicketStatus.in_progress,
    TicketStatus.waiting_info,
}

# Финальные статусы (нельзя менять дальше, кроме resolved → closed)
FINAL_STATUSES = {TicketStatus.rejected, TicketStatus.closed}

ALLOWED_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.new: {
        TicketStatus.in_progress,
        TicketStatus.waiting_info,
        TicketStatus.resolved,
        TicketStatus.rejected,
    },
    TicketStatus.in_progress: {
        TicketStatus.waiting_info,
        TicketStatus.resolved,
        TicketStatus.rejected,
    },
    TicketStatus.waiting_info: {
        TicketStatus.in_progress,
        TicketStatus.resolved,
        TicketStatus.rejected,
    },
    TicketStatus.resolved: {TicketStatus.closed},
    TicketStatus.rejected: set(),
    TicketStatus.closed: set(),
}

_STATUS_RU = {
    TicketStatus.new: "Новая",
    TicketStatus.in_progress: "В работе",
    TicketStatus.waiting_info: "Ожидание информации",
    TicketStatus.resolved: "Решена",
    TicketStatus.rejected: "Отклонена",
    TicketStatus.closed: "Закрыта",
}


def can_transition(current: TicketStatus, new: TicketStatus) -> bool:
    if current == new:
        return True
    allowed = ALLOWED_TRANSITIONS.get(current)
    if not allowed:
        return False
    return new in allowed


def transition_error(current: TicketStatus, new: TicketStatus) -> str:
    if can_transition(current, new):
        return ""
    cur = _STATUS_RU.get(current, current.value)
    nxt = _STATUS_RU.get(new, new.value)
    if current in FINAL_STATUSES or current == TicketStatus.resolved:
        return f"Заявка уже в статусе «{cur}», переход в «{nxt}» невозможен"
    return f"Переход «{cur}» → «{nxt}» не допускается"
