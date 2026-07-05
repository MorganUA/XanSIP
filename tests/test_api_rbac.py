"""Web CRM RBAC: support cannot perform admin mutations."""
from __future__ import annotations

import re

import pytest
from starlette.testclient import TestClient

from db.models.user import User, UserRole


def _login(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("bot.config.settings.web_admin_username", "qa_admin")
    monkeypatch.setattr("bot.config.settings.web_admin_password", "qa_secret")
    cap = client.get("/api/auth/captcha")
    q = cap.json()["question"]
    m = re.match(r"(\d+)\s*\+\s*(\d+)", q)
    answer = str(int(m.group(1)) + int(m.group(2)))
    r = client.post(
        "/api/auth/login",
        json={"username": "qa_admin", "password": "qa_secret", "captcha": answer},
    )
    assert r.status_code == 200, r.text


def _support_user() -> User:
    return User(
        id=999001,
        telegram_id=9_200_000_000_001,
        internal_id="WEB-SUP-TEST",
        role=UserRole.support,
    )


@pytest.fixture
def support_client(client: TestClient, monkeypatch):
    from api.deps import get_web_actor

    _login(client, monkeypatch)

    async def override():
        return _support_user()

    client.app.dependency_overrides[get_web_actor] = override
    yield client
    client.app.dependency_overrides.pop(get_web_actor, None)


@pytest.mark.parametrize(
    "path,body",
    [
        ("/api/users/1/ban", {"reason": "test"}),
        ("/api/users/1/unban", None),
        ("/api/sips", {"telegram_id": 1, "sip_number": "999"}),
        ("/api/sips/1/disable", None),
        ("/api/groups/1/approve", None),
        ("/api/groups/1/freeze", {"reason": "test"}),
        ("/api/settings/softphone", {
            "enabled": False,
            "wss_url": "",
            "sip_domain": "",
            "display_name": "QA",
            "stun_servers": [],
            "turn_url": "",
            "turn_username": "",
            "turn_credential": "",
            "dial_prefix": "",
            "outbound_proxy": "",
            "session_ttl_seconds": 300,
        }),
    ],
)
def test_support_blocked_on_admin_mutations(support_client: TestClient, path, body):
    method = "put" if path.endswith("softphone") else "post"
    r = support_client.request(method, path, json=body or {})
    assert r.status_code == 403, f"{path} -> {r.status_code} {r.text}"
