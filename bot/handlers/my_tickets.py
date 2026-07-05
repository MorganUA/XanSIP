from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters.chat import apply_private_chat_filter
from bot.keyboards.main_menu import get_main_menu
from bot.utils.menu_catalog import BTN_MINI_APP, BTN_MY_SIPS, BTN_MY_TICKETS, BTN_REPORT, TEXTS_MY_TICKETS
from bot.utils.ticket_display import format_ticket_short
from bot.utils.ticket_status import ACTIVE_STATUSES
from bot.utils.webapp import get_mini_app_url
from db.models.ticket import TicketStatus
from db.models.user import User
from db.repositories.ticket_repo import TicketRepository

router = apply_private_chat_filter(Router())

_STATUS_ORDER = (
    TicketStatus.new,
    TicketStatus.in_progress,
    TicketStatus.waiting_info,
    TicketStatus.resolved,
    TicketStatus.rejected,
    TicketStatus.closed,
)


def _sort_tickets(tickets):
    def key(t):
        try:
            pri = _STATUS_ORDER.index(t.status)
        except ValueError:
            pri = 99
        created = t.created_at
        ts = created.timestamp() if created else 0
        return (pri, -ts)
    return sorted(tickets, key=key)


async def _send_my_tickets(message: Message, user: User, session: AsyncSession) -> None:
    repo = TicketRepository(session)
    tickets = await repo.get_by_user_id(user.id, limit=15)
    if not tickets:
        mini = f" или <b>{BTN_MINI_APP}</b>" if get_mini_app_url() else ""
        await message.answer(
            "<b>Мои заявки</b>\n\n"
            "Заявок пока нет.\n"
            f"Создайте через <b>{BTN_REPORT}</b>{mini}.",
            parse_mode="HTML",
            reply_markup=get_main_menu(user),
        )
        return

    active = [t for t in tickets if t.status in ACTIVE_STATUSES]
    lines = ["<b>Мои заявки</b>\n"]
    if active:
        lines.append("<b>Активные:</b>")
        for t in _sort_tickets(active)[:8]:
            lines.append(f"• {format_ticket_short(t)}")
        lines.append("")
    recent_closed = [t for t in tickets if t.status not in ACTIVE_STATUSES][:5]
    if recent_closed:
        lines.append("<b>Недавно закрытые:</b>")
        for t in recent_closed:
            lines.append(f"• {format_ticket_short(t)}")
    lines.append(f"\nСоздать заявку — <b>{BTN_REPORT}</b> или {BTN_MY_SIPS}.")

    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=get_main_menu(user),
    )


@router.message(F.text.in_(TEXTS_MY_TICKETS))
@router.message(Command("tickets"))
async def cmd_my_tickets(message: Message, user: User, session: AsyncSession):
    await _send_my_tickets(message, user, session)
