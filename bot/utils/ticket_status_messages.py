from db.models.ticket import TicketStatus

from bot.utils.formatting import escape_html


def ticket_status_notify_event(status: TicketStatus) -> str:
    if status == TicketStatus.resolved:
        return "ticket_resolved"
    return "ticket_status"


def build_ticket_status_message(
    ticket_id: int,
    status: TicketStatus,
    *,
    comment: str | None = None,
) -> str:
    tid = ticket_id
    extra = f"\n\n💬 {escape_html(comment)}" if comment else ""

    if status == TicketStatus.in_progress:
        return (
            f"🔧 Ваша заявка <b>#{tid}</b> взята в работу.\n"
            f"Мы работаем над решением.{extra}"
        )
    if status == TicketStatus.resolved:
        return (
            f"✅ Ваша заявка <b>#{tid}</b> решена!\n"
            f"Если проблема осталась — создайте новую заявку.{extra}"
        )
    if status == TicketStatus.rejected:
        return (
            f"❌ Заявка <b>#{tid}</b> отклонена.\n"
            f"По вопросам обратитесь к администратору.{extra}"
        )
    if status == TicketStatus.waiting_info:
        return (
            f"❓ По заявке <b>#{tid}</b> требуется дополнительная информация.\n"
            f"Пожалуйста, свяжитесь с администратором.{extra}"
        )
    if status == TicketStatus.closed:
        return f"🔒 Заявка <b>#{tid}</b> закрыта.{extra}"

    label = status.value
    return f"📋 Статус заявки <b>#{tid}</b> изменён: {label}.{extra}"
