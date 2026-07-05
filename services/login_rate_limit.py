"""Redis-backed rate limit for Web CRM login attempts."""

from __future__ import annotations

from fastapi import HTTPException, Request
from redis.asyncio import Redis

FAIL_PREFIX = "login:fail:"
BLOCK_PREFIX = "login:block:"
MAX_FAILURES = 5
FAIL_WINDOW_SEC = 900  # 15 min
BLOCK_SEC = 900


async def check_login_allowed(request: Request, redis: Redis) -> None:
    ip = _client_ip(request)
    if await redis.exists(f"{BLOCK_PREFIX}{ip}"):
        raise HTTPException(
            status_code=429,
            detail="Слишком много попыток входа. Повторите через 15 минут.",
        )


async def record_login_failure(request: Request, redis: Redis) -> None:
    ip = _client_ip(request)
    key = f"{FAIL_PREFIX}{ip}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, FAIL_WINDOW_SEC)
    if count >= MAX_FAILURES:
        await redis.setex(f"{BLOCK_PREFIX}{ip}", BLOCK_SEC, "1")
        await redis.delete(key)


async def clear_login_failures(request: Request, redis: Redis) -> None:
    ip = _client_ip(request)
    await redis.delete(f"{FAIL_PREFIX}{ip}", f"{BLOCK_PREFIX}{ip}")


def _client_ip(request: Request) -> str:
    from services.security import client_ip_from_request

    return client_ip_from_request(request)
