from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from api.auth import AuthMiddleware
from api.routes_finance import router as finance_router
from api.routes_softphone import router as softphone_router
from api.routes_guides import router as guides_router
from api.routes_mini import router as mini_router
from api.routes_notion import router as notion_router
from api.routers.auth import router as auth_router
from api.routers.dashboard import router as dashboard_router
from api.routers.groups import router as groups_router
from api.routers.notifications import router as notifications_router
from api.routers.pages import router as pages_router
from api.routers.sips import router as sips_router
from api.routers.softphone_settings import router as softphone_settings_router
from api.routers.tickets import router as tickets_router
from api.routers.users import router as users_router
from core.config import settings
from db.base import async_session_maker

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="SIP CRM Admin", docs_url="/api/docs", redoc_url=None)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    max_age=86400 * 7,
    same_site="lax",
    https_only=settings.cookie_https_only,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(pages_router)
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(notifications_router)
app.include_router(softphone_settings_router)
app.include_router(users_router)
app.include_router(sips_router)
app.include_router(tickets_router)
app.include_router(groups_router)
app.include_router(mini_router)
app.include_router(softphone_router)
app.include_router(finance_router)
app.include_router(guides_router)
app.include_router(notion_router)


@app.on_event("startup")
async def on_startup_seed_web_accounts():
    import logging
    import os

    from services.security import validate_production_config

    validate_production_config(settings)

    if os.environ.get("SKIP_WEB_ACCOUNT_SEED") == "1":
        return

    from db.migrate import upgrade_head
    from services.web_auth import ensure_web_accounts

    logger = logging.getLogger(__name__)
    upgrade_head()
    async with async_session_maker() as session:
        counts = await ensure_web_accounts(session)
    logger.info("Web accounts ready: %s", counts)
