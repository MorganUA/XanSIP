"""API response contract tests (authenticated, single TestClient session)."""
from __future__ import annotations

import re

import pytest
from starlette.testclient import TestClient

from api.main import app


def _login_client(client: TestClient, monkeypatch) -> TestClient:
    monkeypatch.setattr("bot.config.settings.web_admin_username", "qa_admin")
    monkeypatch.setattr("bot.config.settings.web_admin_password", "qa_secret")
    cap = client.get("/api/auth/captcha")
    q = cap.json()["question"]
    m = re.match(r"(\d+)\s*\+\s*(\d+)", q)
    answer = str(int(m.group(1)) + int(m.group(2)))
    client.post(
        "/api/auth/login",
        json={"username": "qa_admin", "password": "qa_secret", "captcha": answer},
    )
    return client


def test_authenticated_api_contracts(client: TestClient, monkeypatch):
    """One session — avoids asyncpg issues between tests."""
    _login_client(client, monkeypatch)

    sd = client.get("/api/tickets/service-desk")
    assert sd.status_code == 200
    sd_data = sd.json()
    assert isinstance(sd_data.get("items"), list)
    summary = sd_data.get("summary") or {}
    assert "sla_seconds" in summary

    fin = client.get("/api/finance/config")
    assert fin.status_code == 200
    fin_data = fin.json()
    assert "min_deposit_usdt" in fin_data

    dash = client.get("/api/dashboard")
    assert dash.status_code == 200
    dash_data = dash.json()
    for key in ("users_total", "tickets_open", "sips_total", "service_desk_active"):
        assert key in dash_data, key

    sp = client.get("/api/settings/softphone")
    assert sp.status_code == 200
    sp_data = sp.json()
    assert "config" in sp_data
    for key in ("enabled", "wss_url", "sip_domain", "stun_servers"):
        assert key in sp_data["config"], key


def test_authenticated_guides_api(client: TestClient, monkeypatch):
    _login_client(client, monkeypatch)

    r = client.get("/api/guides/operations")
    assert r.status_code == 200
    data = r.json()
    assert data["featured_guide_id"] == "workflow-max-value"
    assert len(data["guides"]) >= 16

    r2 = client.get("/api/guides/operations/workflow-max-value")
    assert r2.status_code == 200
    assert r2.json()["id"] == "workflow-max-value"

    r3 = client.get("/api/guides/operations/nonexistent-guide")
    assert r3.status_code == 404

    for aud in ("workflow", "user", "group_owner", "admin"):
        ra = client.get(f"/api/guides/operations?audience={aud}")
        assert ra.status_code == 200
        assert all(g["audience"] == aud for g in ra.json()["guides"])

    rb = client.get("/api/guides/operations?audience=superuser")
    assert rb.status_code == 400

    rs = client.get("/api/guides/sip-integration")
    assert rs.status_code == 200
    sip = rs.json()
    assert len(sip["guides"]) >= 6
    assert "mor5" in sip["categories"]
