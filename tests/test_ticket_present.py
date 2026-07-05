from api.services.ticket_present import resolve_error_label, _status_label
from db.models.ticket import ErrorType


def test_resolve_group_preset_label():
    label = resolve_error_label("gd_balance", ErrorType.no_balance, "desc")
    assert "баланс" in label.lower() or "Баланс" in label


def test_status_label_ru():
    assert _status_label("in_progress") == "В работе"
    assert _status_label(None) == "—"
