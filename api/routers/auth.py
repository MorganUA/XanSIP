from fastapi import APIRouter, Depends, HTTPException, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import clear_authenticated, is_authenticated, issue_captcha, verify_login
from api.deps import get_redis, get_session
from api.schemas.admin import LoginBody

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/captcha")
async def get_captcha(request: Request):
    return {"question": issue_captcha(request)}


@router.post("/login")
async def login(
    request: Request,
    body: LoginBody,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
):
    from services.login_rate_limit import check_login_allowed, clear_login_failures, record_login_failure

    await check_login_allowed(request, redis)
    try:
        info = await verify_login(request, session, body.username, body.password, body.captcha)
    except HTTPException as exc:
        if exc.status_code in (400, 401):
            await record_login_failure(request, redis)
        raise
    await clear_login_failures(request, redis)
    return {"ok": True, **info}


@router.get("/me")
async def auth_me(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {
        "username": request.session.get("web_username"),
        "role": request.session.get("web_role"),
    }


@router.post("/logout")
async def logout(request: Request):
    clear_authenticated(request)
    return {"ok": True}
