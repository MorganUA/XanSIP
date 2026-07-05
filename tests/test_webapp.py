"""Тесты Web App URL."""

from bot.utils.webapp import get_mini_app_url, is_https_webapp_url


def test_is_https_webapp_url():
    assert is_https_webapp_url("https://crm.example.com/mini")
    assert not is_https_webapp_url("http://185.192.23.225:8000/mini")
    assert not is_https_webapp_url(None)


def test_get_mini_app_url_requires_https(monkeypatch):
    from bot.config import settings
    monkeypatch.setattr(settings, "public_web_url", "http://185.192.23.225:8000")
    assert get_mini_app_url() is None
    monkeypatch.setattr(settings, "public_web_url", "https://crm.example.com")
    assert get_mini_app_url() == "https://crm.example.com/mini"
