import secrets

from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse

from bot.config import settings
from services.web_auth import authenticate

SESSION_AUTH_KEY = "authenticated"
WEB_ACCOUNT_ID_KEY = "web_account_id"
WEB_USERNAME_KEY = "web_username"
WEB_ROLE_KEY = "web_role"
CAPTCHA_ANSWER_KEY = "captcha_answer"

PUBLIC_PATHS = frozenset({
    "/login",
    "/mini",
    "/api/health",
    "/api/auth/login",
    "/api/auth/captcha",
    "/api/tickets/create",
})

PUBLIC_PREFIXES = ("/static/", "/api/mini/")


def is_authenticated(request: Request) -> bool:
    return request.session.get(SESSION_AUTH_KEY) is True


def set_authenticated(request: Request, *, account_id: int | None, username: str, role: str) -> None:
    request.session[SESSION_AUTH_KEY] = True
    request.session[WEB_ACCOUNT_ID_KEY] = account_id
    request.session[WEB_USERNAME_KEY] = username
    request.session[WEB_ROLE_KEY] = role


def clear_authenticated(request: Request) -> None:
    request.session.pop(SESSION_AUTH_KEY, None)
    request.session.pop(WEB_ACCOUNT_ID_KEY, None)
    request.session.pop(WEB_USERNAME_KEY, None)
    request.session.pop(WEB_ROLE_KEY, None)
    request.session.pop(CAPTCHA_ANSWER_KEY, None)


def issue_captcha(request: Request) -> str:
    import random

    a = random.randint(2, 12)
    b = random.randint(2, 12)
    request.session[CAPTCHA_ANSWER_KEY] = str(a + b)
    return f"{a} + {b}"


async def verify_login(
    request: Request,
    session: AsyncSession,
    username: str,
    password: str,
    captcha: str,
) -> dict[str, str]:
    expected = request.session.get(CAPTCHA_ANSWER_KEY)
    request.session.pop(CAPTCHA_ANSWER_KEY, None)

    if not expected or captcha.strip() != expected:
        raise HTTPException(status_code=400, detail="Неверная captcha")

    account = await authenticate(session, username, password)
    if account:
        set_authenticated(
            request,
            account_id=account.id,
            username=account.username,
            role=account.role.value,
        )
        return {
            "username": account.username,
            "role": account.role.value,
            "display_name": account.display_name,
        }

    # Обратная совместимость: единственный суперадмин из .env до миграции
    uname = username.strip()
    if secrets.compare_digest(uname, settings.web_admin_username) and secrets.compare_digest(
        password, settings.web_admin_password
    ):
        set_authenticated(
            request,
            account_id=None,
            username=settings.web_admin_username,
            role="superadmin",
        )
        return {
            "username": settings.web_admin_username,
            "role": "superadmin",
            "display_name": "Главный суперадмин Web SIP",
        }

    raise HTTPException(status_code=401, detail="Неверный логин или пароль")


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in PUBLIC_PATHS:
            return await call_next(request)

        if any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
            return await call_next(request)

        if path.startswith("/api/docs") or path.startswith("/api/openapi"):
            if not is_authenticated(request):
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
            return await call_next(request)

        if path == "/" or path.startswith("/api/"):
            if not is_authenticated(request):
                if path.startswith("/api/"):
                    return JSONResponse({"detail": "Unauthorized"}, status_code=401)
                return RedirectResponse(url="/login", status_code=303)

        return await call_next(request)
