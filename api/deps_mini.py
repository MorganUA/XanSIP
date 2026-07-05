from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from api.services.telegram_webapp import telegram_user_from_init, validate_init_data
from bot.config import settings
from bot.utils.internal_id import generate_unique_internal_id
from db.models.user import User, UserRole
from db.repositories.user_repo import UserRepository


async def get_mini_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: AsyncSession = Depends(get_session),
) -> User:
    if not authorization or not authorization.lower().startswith("tma "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    init_data = authorization[4:].strip()
    parsed = validate_init_data(init_data)
    tg_user = telegram_user_from_init(parsed)
    telegram_id = int(tg_user["id"])

    repo = UserRepository(session)
    user = await repo.get_by_telegram_id(telegram_id)
    if user is None:
        role = (
            UserRole.superadmin
            if telegram_id == settings.superadmin_telegram_id
            else UserRole.user
        )
        internal_id = await generate_unique_internal_id(session)
        user = await repo.create(
            telegram_id=telegram_id,
            internal_id=internal_id,
            username=tg_user.get("username"),
            first_name=tg_user.get("first_name"),
            last_name=tg_user.get("last_name"),
            role=role,
        )
    else:
        await repo.sync_profile(
            user,
            username=tg_user.get("username"),
            first_name=tg_user.get("first_name"),
            last_name=tg_user.get("last_name"),
        )
    if user.is_banned:
        raise HTTPException(status_code=403, detail="Account banned")
    return user
