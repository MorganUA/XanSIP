"""SIP softphone trunk + secret encryption tests."""

import pytest


def test_encrypt_roundtrip():
    from services.sip_secret import decrypt_secret, encrypt_secret

    token = encrypt_secret("s3cret-pass")
    assert decrypt_secret(token) == "s3cret-pass"


def test_trunk_ready_requires_wss_and_domain(monkeypatch):
    monkeypatch.setattr("services.sip_trunk.settings.sip_trunk_enabled", True)
    monkeypatch.setattr("services.sip_trunk.settings.sip_wss_url", "wss://pbx/ws")
    monkeypatch.setattr("services.sip_trunk.settings.sip_domain", "pbx.local")
    from services.sip_trunk import env_trunk_defaults, trunk_is_ready

    cfg = env_trunk_defaults()
    assert trunk_is_ready(cfg)


def test_build_ice_servers_stun_and_turn():
    from services.sip_trunk import build_ice_servers

    cfg = {
        "stun_servers": ["stun:stun.test:19302"],
        "turn_url": "turn:turn.test:3478",
        "turn_username": "u",
        "turn_credential": "p",
    }
    servers = build_ice_servers(cfg)
    assert servers[0]["urls"].startswith("stun:")
    assert servers[1]["username"] == "u"


def test_build_webrtc_session(monkeypatch):
    from db.models.sip_account import SipStatus
    from services.sip_secret import encrypt_secret
    from services.sip_trunk import build_webrtc_session

    monkeypatch.setattr("services.sip_trunk.settings.sip_session_ttl_seconds", 300)

    class _FakeSip:
        id = 7
        sip_number = "100"
        auth_username = "device100"
        auth_secret_enc = encrypt_secret("pass123")
        status = SipStatus.active

    cfg = {
        "enabled": True,
        "wss_url": "wss://pbx/ws",
        "sip_domain": "pbx.local",
        "display_name": "CRM",
        "stun_servers": ["stun:stun.test:19302"],
        "dial_prefix": "",
        "session_ttl_seconds": 300,
    }
    session = build_webrtc_session(_FakeSip(), cfg)
    assert session["uri"] == "sip:device100@pbx.local"
    assert session["password"] == "pass123"
    assert session["wss_url"] == "wss://pbx/ws"
    assert "expires_at" in session


def test_build_webrtc_session_requires_credentials():
    from db.models.sip_account import SipStatus
    from services.sip_trunk import build_webrtc_session

    class _FakeSip:
        id = 1
        sip_number = "100"
        auth_username = None
        auth_secret_enc = None
        status = SipStatus.active

    cfg = {"enabled": True, "wss_url": "wss://x", "sip_domain": "d", "stun_servers": []}
    with pytest.raises(ValueError, match="credentials"):
        build_webrtc_session(_FakeSip(), cfg)
