"""Агрегация статистики и отчётов по работе SIP и заявкам."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.error_labels import ERROR_TYPE_LABELS
from db.models.ticket import ErrorType, TicketSource, TicketStatus
from db.repositories.sip_repo import SipRepository
from db.repositories.ticket_repo import TicketRepository
from db.repositories.user_repo import UserRepository

SOURCE_LABELS = {
    TicketSource.personal_chat: "Личный чат",
    TicketSource.group_chat: "Группа (колл-центр)",
    TicketSource.command: "Команда /err",
}


def _since(days: int) -> datetime:
    d = max(1, min(days, 365))
    return datetime.now(timezone.utc) - timedelta(days=d)


def _fmt_duration(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    s = int(seconds)
    if s < 60:
        return f"{s} сек"
    m, sec = divmod(s, 60)
    if m < 60:
        return f"{m} мин {sec} сек" if sec else f"{m} мин"
    h, m = divmod(m, 60)
    return f"{h} ч {m} мин"


async def build_sip_work_report(session: AsyncSession, *, days: int = 30) -> dict:
    since = _since(days)
    ticket_repo = TicketRepository(session)
    sip_repo = SipRepository(session)
    user_repo = UserRepository(session)

    sip_by_status = await sip_repo.count_by_status()
    tickets_by_status = await ticket_repo.count_by_status()
    open_statuses = (
        TicketStatus.new,
        TicketStatus.in_progress,
        TicketStatus.waiting_info,
    )
    tickets_open = sum(tickets_by_status.get(s.value, 0) for s in open_statuses)

    created = await ticket_repo.count_created_since(since)
    resolved = await ticket_repo.count_resolved_since(since)
    avg_sec = await ticket_repo.avg_resolution_seconds_since(since)

    by_error = await ticket_repo.count_by_error_type_since(since)
    by_source = await ticket_repo.count_by_source_since(since)
    top_sips = await ticket_repo.top_sips_since(since, limit=15)
    agents = await ticket_repo.agent_stats_since(since, limit=10)
    daily = await ticket_repo.daily_counts_since(since)
    sips_with_open = await ticket_repo.sips_with_open_tickets(limit=15)

    agent_rows = []
    for row in agents:
        user = await user_repo.get_by_id(row["user_id"]) if row["user_id"] else None
        agent_rows.append({
            "user_id": row["user_id"],
            "name": (user.first_name or user.username or str(row["user_id"])) if user else "—",
            "internal_id": user.internal_id if user else None,
            "taken": row["taken"],
            "resolved": row["resolved"],
        })

    return {
        "period_days": max(1, min(days, 365)),
        "period_from": since.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sips": {
            "total": sum(sip_by_status.values()),
            "by_status": sip_by_status,
            "active": sip_by_status.get("active", 0),
            "frozen": sip_by_status.get("frozen", 0),
            "disabled": sip_by_status.get("disabled", 0),
        },
        "tickets": {
            "open": tickets_open,
            "by_status": tickets_by_status,
            "created_in_period": created,
            "resolved_in_period": resolved,
            "resolution_rate_pct": round(resolved / created * 100, 1) if created else None,
            "avg_resolution_seconds": avg_sec,
            "avg_resolution_human": _fmt_duration(avg_sec),
        },
        "by_error_type": [
            {
                "error_type": k,
                "label": ERROR_TYPE_LABELS.get(ErrorType(k), k),
                "count": v,
            }
            for k, v in sorted(by_error.items(), key=lambda x: -x[1])
        ],
        "by_source": [
            {"source": k, "label": SOURCE_LABELS.get(TicketSource(k), k), "count": v}
            for k, v in sorted(by_source.items(), key=lambda x: -x[1])
        ],
        "top_sips": top_sips,
        "sips_with_open_tickets": sips_with_open,
        "agents": agent_rows,
        "daily": daily,
    }


def report_to_csv(report: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["SIP CRM — отчёт о работе SIP"])
    w.writerow(["Период (дней)", report["period_days"]])
    w.writerow(["С", report["period_from"]])
    w.writerow(["Сформирован", report["generated_at"]])
    w.writerow([])

    w.writerow(["SIP-номера"])
    w.writerow(["Всего", report["sips"]["total"]])
    for st, cnt in report["sips"]["by_status"].items():
        w.writerow([st, cnt])
    w.writerow([])

    w.writerow(["Заявки за период"])
    t = report["tickets"]
    w.writerow(["Создано", t["created_in_period"]])
    w.writerow(["Решено", t["resolved_in_period"]])
    w.writerow(["Открыто сейчас", t["open"]])
    w.writerow(["Среднее время решения (сек)", t["avg_resolution_seconds"] or ""])
    w.writerow([])

    w.writerow(["По типу ошибки", "Кол-во"])
    for row in report["by_error_type"]:
        w.writerow([row["label"], row["count"]])
    w.writerow([])

    w.writerow(["По источнику", "Кол-во"])
    for row in report["by_source"]:
        w.writerow([row["label"], row["count"]])
    w.writerow([])

    w.writerow(["Топ SIP по заявкам", "Заявок", "Открытых"])
    for row in report["top_sips"]:
        w.writerow([row["sip_number"], row["total"], row.get("open", 0)])
    w.writerow([])

    w.writerow(["SIP с открытыми заявками", "Открытых"])
    for row in report["sips_with_open_tickets"]:
        w.writerow([row["sip_number"], row["open"]])
    w.writerow([])

    w.writerow(["Агент", "Internal ID", "Взято", "Решено"])
    for row in report["agents"]:
        w.writerow([row["name"], row.get("internal_id") or "", row["taken"], row["resolved"]])
    w.writerow([])

    w.writerow(["Дата", "Создано", "Решено"])
    for row in report["daily"]:
        w.writerow([row["date"], row["created"], row["resolved"]])

    return buf.getvalue()


def format_stats_telegram(report: dict) -> str:
    t = report["tickets"]
    s = report["sips"]
    lines = [
        f"📈 <b>Статистика SIP ({report['period_days']} дн.)</b>\n",
        f"📞 SIP: <b>{s['active']}</b> акт. / {s['total']} всего "
        f"(замор. {s['frozen']}, откл. {s['disabled']})",
        f"🎫 Заявок: <b>{t['created_in_period']}</b> создано · "
        f"<b>{t['resolved_in_period']}</b> решено",
        f"⏱ Среднее решение: {t['avg_resolution_human'] or '—'}",
        f"📂 Открыто сейчас: <b>{t['open']}</b>",
    ]
    if t["resolution_rate_pct"] is not None:
        lines.append(f"✅ Доля решённых: {t['resolution_rate_pct']}%")

    if report["by_error_type"]:
        lines.append("\n<b>Типы ошибок:</b>")
        for row in report["by_error_type"][:5]:
            lines.append(f"• {row['label']}: {row['count']}")

    if report["top_sips"]:
        lines.append("\n<b>Топ SIP по заявкам:</b>")
        for row in report["top_sips"][:5]:
            open_part = f", {row['open']} откр." if row.get("open") else ""
            lines.append(f"• <code>{row['sip_number']}</code> — {row['total']}{open_part}")

    if report["sips_with_open_tickets"]:
        lines.append("\n<b>SIP с открытыми заявками:</b>")
        for row in report["sips_with_open_tickets"][:5]:
            lines.append(f"• <code>{row['sip_number']}</code> — {row['open']}")

    lines.append("\n📊 Полный отчёт и CSV: Web CRM → <b>Статистика SIP</b>")
    lines.append("Период: /stats 7 · /stats 30 · /stats 90")
    return "\n".join(lines)
