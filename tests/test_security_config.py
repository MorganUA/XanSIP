"""Tests for production security validation."""
from __future__ import annotations

import os

import pytest

from bot.config import Settings
from services.security import build_redis_url, is_production_env, validate_production_config


def test_build_redis_url_with_password():
    assert build_redis_url(password="s3cret") == "redis://:s3cret@redis:6379/0"


def test_build_redis_url_without_password():
    assert build_redis_url() == "redis://redis:6379/0"


def test_production_validation_skipped_in_development(monkeypatch):
    monkeypatch.delenv("SIPCRM_ENV", raising=False)
    s = Settings(
        bot_token="x",
        support_group_id=1,
        superadmin_telegram_id=1,
        database_url="postgresql+asyncpg://u:p@localhost/db",
        redis_url="redis://localhost/0",
        secret_key="change-me-dev-only",
        bot_api_secret="change-me-dev-bot-secret",
        web_admin_password="change-me-dev-only",
        sipcrm_env="development",
    )
    validate_production_config(s)  # no raise


def test_production_validation_rejects_weak_secrets(monkeypatch):
    monkeypatch.setenv("SIPCRM_ENV", "production")
    monkeypatch.setenv("WEB_ADMIN_PRIV_PASSWORD", "SipAdm2026!")
    monkeypatch.setenv("WEB_ADMIN_SUPPORT_PASSWORD", "SipSup2026!")
    monkeypatch.setenv("REDIS_PASSWORD", "short")

    s = Settings(
        bot_token="x",
        support_group_id=1,
        superadmin_telegram_id=1,
        database_url="postgresql+asyncpg://u:p@localhost/db",
        redis_url="redis://localhost/0",
        secret_key="change-me",
        bot_api_secret="change-me-bot-secret",
        web_admin_password="weak",
        sipcrm_env="production",
    )
    with pytest.raises(SystemExit):
        validate_production_config(s)


def test_cookie_https_only_from_public_url(monkeypatch):
    monkeypatch.setenv("PUBLIC_WEB_URL", "https://crm.example.com")
    s = Settings(
        bot_token="x",
        support_group_id=1,
        superadmin_telegram_id=1,
        database_url="postgresql+asyncpg://u:p@localhost/db",
        redis_url="redis://localhost/0",
        public_web_url="https://crm.example.com",
    )
    assert s.cookie_https_only is True
