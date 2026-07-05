from bot.services.sip_work_stats import report_to_csv


def _sample_report() -> dict:
    return {
        "period_days": 7,
        "period_from": "2026-01-01T00:00:00+00:00",
        "generated_at": "2026-01-08T12:00:00+00:00",
        "sips": {
            "total": 10,
            "by_status": {"active": 8, "disabled": 2},
            "active": 8,
            "frozen": 0,
            "disabled": 2,
        },
        "tickets": {
            "open": 3,
            "by_status": {},
            "created_in_period": 12,
            "resolved_in_period": 9,
            "resolution_rate_pct": 75.0,
            "avg_resolution_seconds": 180.5,
            "avg_resolution_human": "3 мин",
        },
        "by_error_type": [{"label": "Нет баланса", "count": 5}],
        "by_source": [{"label": "Группа", "count": 8}],
        "top_sips": [{"sip_number": "100", "total": 4, "open": 1}],
        "sips_with_open_tickets": [{"sip_number": "100", "open": 1}],
        "agents": [{"name": "Agent", "internal_id": "A1", "taken": 5, "resolved": 4}],
        "daily": [{"date": "2026-01-07", "created": 2, "resolved": 1}],
    }


def test_report_to_csv_contains_sections():
    csv_text = report_to_csv(_sample_report())
    assert "SIP CRM" in csv_text
    assert "Нет баланса" in csv_text
    assert "100" in csv_text
    assert "Agent" in csv_text
