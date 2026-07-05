import secrets

from fastapi import Header, HTTPException

from bot.config import settings


def verify_bot_secret(x_bot_secret: str = Header(default="")) -> None:
    if not secrets.compare_digest(x_bot_secret, settings.bot_api_secret):
        raise HTTPException(status_code=403, detail="Invalid bot secret")
