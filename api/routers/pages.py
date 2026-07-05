from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from api.auth import is_authenticated
from core.config import settings

router = APIRouter(tags=["pages"])

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
MINI_DIR = STATIC_DIR / "mini"


@router.get("/mini", response_class=HTMLResponse)
async def mini_app_page():
    path = MINI_DIR / "index.html"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Mini app not found")
    return HTMLResponse(path.read_text(encoding="utf-8"))


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/", status_code=303)
    return HTMLResponse(STATIC_DIR.joinpath("login.html").read_text(encoding="utf-8"))


@router.get("/", response_class=HTMLResponse)
async def admin_panel(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return HTMLResponse(STATIC_DIR.joinpath("index.html").read_text(encoding="utf-8"))


@router.get("/api/health")
async def health():
    return {"status": "ok", "test_mode": settings.test_mode}
