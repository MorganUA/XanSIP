"""Pytest bootstrap: project root on sys.path for `api`, `bot`, `db`, `services`."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("SKIP_WEB_ACCOUNT_SEED", "1")
os.environ.setdefault("SIPCRM_ENV", "development")

ROOT = Path(__file__).resolve().parents[1]
root_str = str(ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)


@pytest.fixture(autouse=True)
def _disable_login_rate_limit(monkeypatch):
    """Tests share TestClient IP — avoid 429 between login attempts."""

    async def _noop(*_args, **_kwargs):
        return None

    for target in (
        "services.login_rate_limit.check_login_allowed",
        "services.login_rate_limit.record_login_failure",
        "services.login_rate_limit.clear_login_failures",
    ):
        monkeypatch.setattr(target, _noop)


@pytest.fixture
def client(monkeypatch):
    """TestClient с обходом web_accounts (asyncpg loop в тестах)."""
    from starlette.testclient import TestClient

    async def _no_db_authenticate(session, username, password):
        return None

    monkeypatch.setattr("api.auth.authenticate", _no_db_authenticate)

    from api.main import app

    with TestClient(app) as test_client:
        yield test_client
