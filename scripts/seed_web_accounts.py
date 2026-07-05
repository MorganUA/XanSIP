#!/usr/bin/env python3
"""Создать/обновить учётные записи Web CRM (roof + admin01-05 + support01-05)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.base import async_session_maker
from services.web_auth import (
    PRIVILEGED_USERNAMES,
    SUPPORT_USERNAMES,
    ensure_web_accounts,
)


async def main() -> int:
    async with async_session_maker() as session:
        counts = await ensure_web_accounts(session)
    print("Web accounts ready:", counts)
    print()
    print("Главный суперадмин: WEB_ADMIN_USERNAME / WEB_ADMIN_PASSWORD (.env)")
    print("Привилегированные (admin):", ", ".join(PRIVILEGED_USERNAMES))
    print("  пароль: WEB_ADMIN_PRIV_PASSWORD (по умолчанию SipAdm2026!)")
    print("Обычные (support):", ", ".join(SUPPORT_USERNAMES))
    print("  пароль: WEB_ADMIN_SUPPORT_PASSWORD (по умолчанию SipSup2026!)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
