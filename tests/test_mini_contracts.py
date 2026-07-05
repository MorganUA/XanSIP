"""Mini App API contracts and static assets."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
MINI_DIR = ROOT / "api" / "static" / "mini"


def _mini_user():
    from db.models.user import User, UserRole

    return User(
        id=888001,
        telegram_id=9_100_000_001,
        internal_id="MINI-QA",
        first_name="Mini",
        role=UserRole.user,
        is_banned=False,
    )


@pytest.fixture
def mini_client(client: TestClient):
    from api.deps_mini import get_mini_user

    async def override():
        return _mini_user()

    client.app.dependency_overrides[get_mini_user] = override
    yield client
    client.app.dependency_overrides.pop(get_mini_user, None)


def test_mini_static_assets():
    assert (MINI_DIR / "index.html").is_file()
    assert (MINI_DIR / "mini.js").is_file()
    assert (MINI_DIR / "softphone.mjs").is_file()
    assert not (MINI_DIR / "softphone.js").is_file()
    html = (MINI_DIR / "index.html").read_text(encoding="utf-8")
    assert 'data-tab="phone"' in html
    assert "jssip" not in html.lower()
    js = (MINI_DIR / "mini.js").read_text(encoding="utf-8")
    assert "bootstrap" in js
    assert "softphone.mjs" in js


def test_mini_bootstrap_requires_auth(client: TestClient):
    r = client.get("/api/mini/bootstrap")
    assert r.status_code == 401


def test_mini_bootstrap_schema(mini_client: TestClient, monkeypatch):
    async def _fake_bootstrap(session, user):
        return {
            "user": {"id": 1, "telegram_id": 1, "internal_id": "X", "first_name": "T", "username": None, "role": "user"},
            "sips_count": 1,
            "open_tickets": 0,
            "quick_presets": [{"id": "gd_fraud", "button": "x", "label": "y"}],
            "extra_presets": [],
            "is_staff": False,
            "sips": [{"id": 1, "sip_number": "100", "description": None, "status": "active", "open_ticket_id": None}],
            "softphone": {"enabled": False, "trunk": {}, "lines": []},
        }

    monkeypatch.setattr("api.routes_mini.build_mini_bootstrap", _fake_bootstrap)
    r = mini_client.get("/api/mini/bootstrap")
    assert r.status_code == 200
    data = r.json()
    for key in ("user", "sips", "softphone", "quick_presets", "sips_count", "open_tickets"):
        assert key in data


def test_mini_page_served(client: TestClient):
    r = client.get("/mini")
    assert r.status_code == 200
    assert "SIP CRM" in r.text
    assert 'data-tab="phone"' in r.text


def test_softphone_status_schema(mini_client: TestClient, monkeypatch):
    async def _fake_summary(session, user_id):
        return {"enabled": False, "trunk": {"display_name": "CRM"}, "lines": []}

    monkeypatch.setattr("api.routes_softphone.build_softphone_summary", _fake_summary)
    r = mini_client.get("/api/mini/softphone/status")
    assert r.status_code == 200
    assert "lines" in r.json()


def test_web_crm_softphone_section_in_html():
    html = (ROOT / "api" / "static" / "index.html").read_text(encoding="utf-8")
    assert 'data-section="softphone"' in html
    assert "softphone-form" in html


def test_web_crm_softphone_js_hooks():
    js = (ROOT / "api" / "static" / "app.js").read_text(encoding="utf-8")
    assert "loadSoftphoneSettings" in js
    m = re.search(r"const SECTION_TITLES = \{([^}]+)\}", js, re.DOTALL)
    assert m and "softphone" in m.group(1)
