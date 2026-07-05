"""Web CRM: хеш паролей, аутентификация, начальные учётные записи."""

from __future__ import annotations

import hashlib
import os
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from db.models.user import User, UserRole
from db.models.web_account import WebAccount
from db.repositories.user_repo import UserRepository
from db.repositories.web_account_repo import WebAccountRepository

PRIVILEGED_USERNAMES = ("admin01", "admin02", "admin03", "admin04", "admin05")
SUPPORT_USERNAMES = ("support01", "support02", "support03", "support04", "support05")

# Синтетические telegram_id для web-only акторов (вне реальных ID Telegram)
PRIV_TELEGRAM_BASE = 9_100_000_000_001
SUPPORT_TELEGRAM_BASE = 9_200_000_000_001


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt, digest_hex = stored.split("$", 2)
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return secrets.compare_digest(check.hex(), digest_hex)


async def authenticate(
    session: AsyncSession,
    username: str,
    password: str,
) -> WebAccount | None:
    repo = WebAccountRepository(session)
    account = await repo.get_by_username(username.strip().lower())
    if not account or not account.is_active:
        return None
    if not verify_password(password, account.password_hash):
        return None
    return account


async def _ensure_actor_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    internal_id: str,
    role: UserRole,
    display_name: str,
) -> User:
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(telegram_id)
    if user:
        if user.role != role:
            user.role = role
            await session.commit()
        return user
    return await user_repo.create(
        telegram_id=telegram_id,
        internal_id=internal_id,
        username=None,
        first_name=display_name,
        role=role,
    )


async def _upsert_account(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    role: UserRole,
    display_name: str,
    telegram_id: int,
    internal_id: str,
    is_primary: bool = False,
) -> WebAccount:
    username = username.strip().lower()
    repo = WebAccountRepository(session)
    actor = await _ensure_actor_user(
        session,
        telegram_id=telegram_id,
        internal_id=internal_id,
        role=role,
        display_name=display_name,
    )
    existing = await repo.get_by_username(username)
    if existing:
        existing.role = role
        existing.display_name = display_name
        existing.actor_user_id = actor.id
        existing.is_primary = is_primary
        existing.is_active = True
        if password and not verify_password(password, existing.password_hash):
            existing.password_hash = hash_password(password)
        await session.commit()
        await session.refresh(existing)
        return existing

    account = WebAccount(
        username=username,
        password_hash=hash_password(password),
        role=role,
        display_name=display_name,
        actor_user_id=actor.id,
        is_primary=is_primary,
        is_active=True,
    )
    return await repo.create(account)


async def ensure_web_accounts(session: AsyncSession) -> dict[str, int]:
    """Идемпотентно создаёт roof + 5 admin + 5 support. Возвращает счётчики."""
    user_repo = UserRepository(session)
    primary_username = os.environ.get(
        "WEB_ADMIN_USERNAME", settings.web_admin_username,
    ).strip().lower()
    priv_password = os.environ.get("WEB_ADMIN_PRIV_PASSWORD", "")
    support_password = os.environ.get("WEB_ADMIN_SUPPORT_PASSWORD", "")
    if not priv_password and not settings.is_production:
        priv_password = "SipAdm2026!"
    if not support_password and not settings.is_production:
        support_password = "SipSup2026!"

    superadmin = await user_repo.get_by_telegram_id(settings.superadmin_telegram_id)
    if not superadmin:
        superadmin = await user_repo.create(
            telegram_id=settings.superadmin_telegram_id,
            internal_id="WEB-SA-PRIMARY",
            first_name="Web Superadmin",
            role=UserRole.superadmin,
        )
    elif superadmin.role != UserRole.superadmin:
        superadmin.role = UserRole.superadmin
        await session.commit()

    await _upsert_account(
        session,
        username=primary_username,
        password=settings.web_admin_password,
        role=UserRole.superadmin,
        display_name="Главный суперадмин Web SIP",
        telegram_id=settings.superadmin_telegram_id,
        internal_id=superadmin.internal_id,
        is_primary=True,
    )

    # Снять primary с прочих (например, после тестов pytest)
    from sqlalchemy import update
    from db.models.web_account import WebAccount

    await session.execute(
        update(WebAccount)
        .where(WebAccount.username != primary_username)
        .values(is_primary=False)
    )
    await session.commit()

    created = {"superadmin": 1, "privileged": 0, "support": 0}
    for i, name in enumerate(PRIVILEGED_USERNAMES, 1):
        await _upsert_account(
            session,
            username=name,
            password=priv_password,
            role=UserRole.admin,
            display_name=f"Администратор {name}",
            telegram_id=PRIV_TELEGRAM_BASE + i,
            internal_id=f"WEB-ADM-{i:02d}",
        )
        created["privileged"] += 1

    for i, name in enumerate(SUPPORT_USERNAMES, 1):
        await _upsert_account(
            session,
            username=name,
            password=support_password,
            role=UserRole.support,
            display_name=f"Оператор {name}",
            telegram_id=SUPPORT_TELEGRAM_BASE + i,
            internal_id=f"WEB-SUP-{i:02d}",
        )
        created["support"] += 1

    return created
