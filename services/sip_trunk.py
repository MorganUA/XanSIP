"""SIP trunk configuration for WebRTC softphone (Mini App)."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.models.sip_account import SipAccount, SipStatus
from db.repositories.app_setting_repo import AppSettingRepository
from services.sip_secret import decrypt_secret

SOFTPHONE_SETTINGS_KEY = "softphone_trunk"
TRUNK_CACHE_TTL_SECONDS = 30
_trunk_cache: tuple[float, dict[str, Any]] | None = None

DEFAULT_TRUNK = {
    "enabled": False,
    "wss_url": "",
    "sip_domain": "",
    "display_name": "SIP CRM",
    "stun_servers": ["stun:stun.l.google.com:19302"],
    "turn_url": "",
    "turn_username": "",
    "turn_credential": "",
    "dial_prefix": "",
    "outbound_proxy": "",
    "session_ttl_seconds": 300,
}


def _parse_stun(raw: str) -> list[str]:
    if not raw.strip():
        return list(DEFAULT_TRUNK["stun_servers"])
    return [part.strip() for part in raw.split(",") if part.strip()]


def env_trunk_defaults() -> dict[str, Any]:
    return {
        "enabled": settings.sip_trunk_enabled,
        "wss_url": settings.sip_wss_url.strip(),
        "sip_domain": settings.sip_domain.strip(),
        "display_name": settings.sip_display_name.strip() or "SIP CRM",
        "stun_servers": _parse_stun(settings.sip_stun_servers),
        "turn_url": settings.sip_turn_url.strip(),
        "turn_username": settings.sip_turn_username.strip(),
        "turn_credential": settings.sip_turn_credential.strip(),
        "dial_prefix": settings.sip_dial_prefix.strip(),
        "outbound_proxy": settings.sip_outbound_proxy.strip(),
        "session_ttl_seconds": settings.sip_session_ttl_seconds,
    }


def merge_trunk_config(stored: dict | None) -> dict[str, Any]:
    cfg = env_trunk_defaults()
    if not stored:
        return cfg
    if "enabled" in stored:
        cfg["enabled"] = bool(stored["enabled"])
    for key in (
        "wss_url", "sip_domain", "display_name", "turn_url",
        "turn_username", "turn_credential", "dial_prefix", "outbound_proxy",
    ):
        if stored.get(key):
            cfg[key] = str(stored[key]).strip()
    if isinstance(stored.get("stun_servers"), list) and stored["stun_servers"]:
        cfg["stun_servers"] = [str(x).strip() for x in stored["stun_servers"] if str(x).strip()]
    if stored.get("session_ttl_seconds"):
        cfg["session_ttl_seconds"] = max(60, min(int(stored["session_ttl_seconds"]), 900))
    return cfg


async def get_trunk_config(session: AsyncSession | None = None) -> dict[str, Any]:
    global _trunk_cache
    if session is None:
        return env_trunk_defaults()
    now = time.monotonic()
    if _trunk_cache and now - _trunk_cache[0] < TRUNK_CACHE_TTL_SECONDS:
        return dict(_trunk_cache[1])
    repo = AppSettingRepository(session)
    stored = await repo.get_value(SOFTPHONE_SETTINGS_KEY)
    cfg = merge_trunk_config(stored)
    _trunk_cache = (now, cfg)
    return cfg


async def save_trunk_config(session: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    global _trunk_cache
    cfg = merge_trunk_config(data)
    repo = AppSettingRepository(session)
    await repo.set_value(
        SOFTPHONE_SETTINGS_KEY,
        cfg,
        description="SIP trunk / WebRTC softphone settings",
    )
    _trunk_cache = (time.monotonic(), cfg)
    return cfg


def trunk_is_ready(cfg: dict[str, Any]) -> bool:
    return bool(cfg.get("enabled") and cfg.get("wss_url") and cfg.get("sip_domain"))


def build_ice_servers(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    servers: list[dict[str, Any]] = [{"urls": url} for url in cfg.get("stun_servers") or []]
    turn_url = cfg.get("turn_url") or ""
    if turn_url:
        entry: dict[str, Any] = {"urls": turn_url}
        if cfg.get("turn_username"):
            entry["username"] = cfg["turn_username"]
        if cfg.get("turn_credential"):
            entry["credential"] = cfg["turn_credential"]
        servers.append(entry)
    return servers


def sip_auth_username(sip: SipAccount) -> str:
    if sip.auth_username:
        return sip.auth_username.strip()
    return sip.sip_number.strip()


def sip_has_credentials(sip: SipAccount) -> bool:
    return bool(sip.auth_secret_enc)


def build_webrtc_session(
    sip: SipAccount,
    cfg: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    if sip.status != SipStatus.active:
        raise ValueError("SIP account is not active")
    if not sip_has_credentials(sip):
        raise ValueError("SIP registration credentials are not configured")
    if not trunk_is_ready(cfg):
        raise ValueError("SIP trunk is not configured")

    domain = cfg["sip_domain"]
    username = sip_auth_username(sip)
    password = decrypt_secret(sip.auth_secret_enc)
    ttl = int(cfg.get("session_ttl_seconds") or settings.sip_session_ttl_seconds)
    expires = (now or datetime.now(timezone.utc)) + timedelta(seconds=ttl)

    uri = f"sip:{username}@{domain}"
    session: dict[str, Any] = {
        "sip_id": sip.id,
        "display_number": sip.sip_number,
        "auth_username": username,
        "uri": uri,
        "password": password,
        "wss_url": cfg["wss_url"],
        "sip_domain": domain,
        "display_name": cfg.get("display_name") or sip.sip_number,
        "ice_servers": build_ice_servers(cfg),
        "dial_prefix": cfg.get("dial_prefix") or "",
        "expires_at": expires.isoformat(),
        "session_ttl_seconds": ttl,
    }
    if cfg.get("outbound_proxy"):
        session["outbound_proxy"] = cfg["outbound_proxy"]
    return session
