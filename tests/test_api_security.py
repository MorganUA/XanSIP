"""API auth boundaries and protected routes (TestClient)."""
from __future__ import annotations

import re

import pytest
from starlette.testclient import TestClient


def test_health_public(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.parametrize(
    "path",
    [
        "/api/dashboard",
        "/api/guides/sip-integration",
        "/api/finance/config",
        "/api/notion/status",
        "/api/audit",
    ],
)
def test_protected_routes_require_auth(client: TestClient, path: str):
    r = client.get(path)
    assert r.status_code == 401, path


def _login(client: TestClient, username: str, password: str) -> None:
    cap = client.get("/api/auth/captcha")
    assert cap.status_code == 200
    question = cap.json()["question"]
    m = re.match(r"(\d+)\s*\+\s*(\d+)", question)
    assert m, question
    answer = str(int(m.group(1)) + int(m.group(2)))
    r = client.post(
        "/api/auth/login",
        json={"username": username, "password": password, "captcha": answer},
    )
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True


def test_login_bad_password_rejected(client: TestClient, monkeypatch):
    monkeypatch.setattr("bot.config.settings.web_admin_username", "qa_admin")
    monkeypatch.setattr("bot.config.settings.web_admin_password", "qa_secret")
    cap = client.get("/api/auth/captcha")
    q = cap.json()["question"]
    m = re.match(r"(\d+)\s*\+\s*(\d+)", q)
    answer = str(int(m.group(1)) + int(m.group(2)))
    r = client.post(
        "/api/auth/login",
        json={"username": "qa_admin", "password": "wrong", "captcha": answer},
    )
    assert r.status_code in (400, 401, 403, 422)


def test_operations_guides_require_auth(client: TestClient):
    r = client.get("/api/guides/operations/workflow-max-value")
    assert r.status_code == 401


def test_sip_guides_authenticated(client: TestClient, monkeypatch):
    monkeypatch.setattr("bot.config.settings.web_admin_username", "qa_admin")
    monkeypatch.setattr("bot.config.settings.web_admin_password", "qa_secret")
    _login(client, "qa_admin", "qa_secret")
    r = client.get("/api/guides/sip-integration")
    assert r.status_code == 200
    data = r.json()
    assert len(data["guides"]) >= 6
    assert "mor5" in data["categories"]
    assert all("kolmisoft.com" in src["url"] or "3cx.com" in src["url"] for g in data["guides"] for src in g["sources"])
