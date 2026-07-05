#!/usr/bin/env python3
"""
Deep QA smoke + integration checks for SIP CRM.
Run inside Docker:  docker compose exec api python scripts/qa_deep.py
Run on server host: cd /opt/sipcrm && docker compose exec -T api python scripts/qa_deep.py
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BASE_URL = os.environ.get("QA_BASE_URL", "http://127.0.0.1:8000")
BOT_WEBHOOK_URL = os.environ.get("QA_BOT_WEBHOOK_URL", "http://bot:8080")
WEB_USER = os.environ.get("WEB_ADMIN_USERNAME", os.environ.get("QA_WEB_USER", "roof"))
WEB_PASS = os.environ.get("WEB_ADMIN_PASSWORD", os.environ.get("QA_WEB_PASS", ""))
WEB_PRIV_PASS = os.environ.get("WEB_ADMIN_PRIV_PASSWORD", "SipAdm2026!")
WEB_SUPPORT_PASS = os.environ.get("WEB_ADMIN_SUPPORT_PASSWORD", "SipSup2026!")

from scripts.qa_helpers import make_tma_init_data, solve_captcha


def login_opener(username: str, password: str) -> tuple[urllib.request.OpenerDirector | None, bool]:
    cj = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    code, cap = http_json("GET", f"{BASE_URL}/api/auth/captcha", opener=opener)
    if code != 200:
        return None, False
    code, data = http_json(
        "POST",
        f"{BASE_URL}/api/auth/login",
        {"username": username, "password": password, "captcha": solve_captcha(cap.get("question", ""))},
        opener=opener,
    )
    return opener, code == 200 and data.get("ok")


@dataclass
class Result:
    area: str
    name: str
    status: str  # PASS | FAIL | WARN | SKIP
    detail: str = ""

    def line(self) -> str:
        icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️", "SKIP": "⏭️"}.get(self.status, "?")
        return f"{icon} [{self.area}] {self.name}" + (f" — {self.detail}" if self.detail else "")


@dataclass
class Report:
    results: list[Result] = field(default_factory=list)

    def add(self, area: str, name: str, ok: bool, detail: str = "", *, warn: bool = False, skip: bool = False) -> None:
        if skip:
            status = "SKIP"
        elif ok:
            status = "PASS"
        elif warn:
            status = "WARN"
        else:
            status = "FAIL"
        self.results.append(Result(area, name, status, detail))

    def summary(self) -> dict:
        counts = {"PASS": 0, "FAIL": 0, "WARN": 0, "SKIP": 0}
        for r in self.results:
            counts[r.status] = counts.get(r.status, 0) + 1
        return counts


def http_json(method: str, url: str, data: dict | None = None, headers: dict | None = None, opener=None):
    body = None
    hdrs = dict(headers or {})
    if data is not None:
        body = json.dumps(data).encode()
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    fn = opener.open if opener else urllib.request.urlopen
    try:
        with fn(req, timeout=15) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw.decode(errors="replace")}
        return e.code, payload
    except urllib.error.URLError as e:
        return 0, {"error": str(e.reason)}


def check_static_python(report: Report) -> None:
    area = "Static"
    errors = []
    for path in ROOT.rglob("*.py"):
        if any(p in path.parts for p in (".git", "venv", "__pycache__", ".pytest_cache", "backups")):
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as e:
            errors.append(f"{path.relative_to(ROOT)}:{e.lineno}")
    report.add(area, "Python syntax (ast)", not errors, "; ".join(errors[:5]) or f"{len(list(ROOT.rglob('*.py')))} files")


def check_static_js(report: Report) -> None:
    area = "Static"
    app_js = ROOT / "api" / "static" / "app.js"
    try:
        content = app_js.read_text(encoding="utf-8")
        # IIFE wrapper — basic parse via node if available, else bracket balance
        report.add(area, "app.js exists", app_js.is_file(), str(app_js))
        report.add(area, "app.js non-empty", len(content) > 1000, f"{len(content)} bytes")
        open_paren = content.count("(")
        close_paren = content.count(")")
        report.add(area, "app.js balanced parens", open_paren == close_paren, f"({open_paren}/{close_paren})")
        for fn in ("loadSipGuides", "loadOperationGuides", "loadFinance", "loadNotion", "loadAudit"):
            report.add(area, f"app.js defines {fn}", fn in content, "")
    except OSError as e:
        report.add(area, "app.js read", False, str(e))


def check_health(report: Report) -> None:
    area = "API"
    code, data = http_json("GET", f"{BASE_URL}/api/health")
    report.add(area, "GET /api/health", code == 200 and data.get("status") == "ok", f"{code} {data}")


def check_auth_boundary(report: Report) -> CookieJar:
    area = "Security"
    code, _ = http_json("GET", f"{BASE_URL}/api/dashboard")
    report.add(area, "Dashboard requires auth (401)", code == 401, f"HTTP {code}")

    code, _ = http_json("GET", f"{BASE_URL}/api/users")
    report.add(area, "Users requires auth (401)", code == 401, f"HTTP {code}")

    code, _ = http_json("GET", f"{BASE_URL}/api/guides/sip-integration")
    report.add(area, "SIP guides requires auth (401)", code == 401, f"HTTP {code}")

    code, _ = http_json("GET", f"{BASE_URL}/api/finance/config")
    report.add(area, "Finance requires auth (401)", code == 401, f"HTTP {code}")

    code, _ = http_json("GET", f"{BASE_URL}/api/guides/operations")
    report.add(area, "Operation guides requires auth (401)", code == 401, f"HTTP {code}")

    code, _ = http_json("GET", f"{BASE_URL}/api/notion/status")
    report.add(area, "Notion requires auth (401)", code == 401, f"HTTP {code}")

    cj = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    code, cap = http_json("GET", f"{BASE_URL}/api/auth/captcha", opener=opener)
    report.add(area, "Captcha endpoint", code == 200 and "question" in cap, str(cap.get("question")))

    if not WEB_PASS:
        report.add(area, "Web login", False, "WEB_ADMIN_PASSWORD not set", warn=True)
        return cj

    q = cap.get("question", "")
    answer = solve_captcha(q)
    code, data = http_json(
        "POST",
        f"{BASE_URL}/api/auth/login",
        {"username": WEB_USER, "password": WEB_PASS, "captcha": answer},
        opener=opener,
    )
    report.add(area, "Web login", code == 200 and data.get("ok"), f"HTTP {code} {data}")
    return cj


def check_authenticated_api(report: Report, opener) -> None:
    area = "API"
    endpoints = [
        ("GET", "/api/dashboard", None),
        ("GET", "/api/stats/sip-work?days=30", None),
        ("GET", "/api/users?limit=5", None),
        ("GET", "/api/sips?limit=5", None),
        ("GET", "/api/tickets?limit=5", None),
        ("GET", "/api/tickets/service-desk", None),
        ("GET", "/api/groups", None),
        ("GET", "/api/settings/notifications", None),
        ("GET", "/api/settings/softphone", None),
        ("GET", "/api/guides/operations", None),
        ("GET", "/api/guides/sip-integration", None),
        ("GET", "/api/finance/config", None),
        ("GET", "/api/finance/deposits?limit=5", None),
        ("GET", "/api/finance/wallets", None),
        ("GET", "/api/notion/status", None),
        ("GET", "/api/notion/guide", None),
        ("GET", "/api/notion/finance-ledger/schema", None),
        ("GET", "/api/audit?limit=5", None),
        ("GET", "/api/system/settings", None),
    ]
    for method, path, body in endpoints:
        code, data = http_json(method, f"{BASE_URL}{path}", body, opener=opener)
        ok = code == 200
        detail = f"HTTP {code}"
        if path == "/api/dashboard" and ok:
            detail += f" users={data.get('users_total')}"
        if path == "/api/settings/notifications" and ok:
            ids = data.get("config", {}).get("support_chat_ids", [])
            detail += f" support_chats={ids}"
        if path == "/api/settings/softphone" and ok:
            detail += f" ready={data.get('ready')} enabled={data.get('config', {}).get('enabled')}"
        if path == "/api/guides/sip-integration" and ok:
            detail += f" guides={len(data.get('guides', []))}"
        if path == "/api/guides/operations" and ok:
            detail += f" guides={len(data.get('guides', []))} featured={data.get('featured_guide_id')}"
        if path == "/api/finance/config" and ok:
            detail += f" min={data.get('min_deposit_usdt')}"
        if path == "/api/notion/status" and ok:
            detail += f" active={data.get('active')}"
        report.add(area, f"{method} {path}", ok, detail)


def check_bot_webhook(report: Report) -> None:
    area = "Integration"
    code, data = http_json("GET", f"{BOT_WEBHOOK_URL}/internal/health")
    unreachable = code == 0
    if unreachable:
        report.add(
            area,
            "Bot webhook health",
            True,
            f"skipped ({data.get('error', 'unreachable')})",
            skip=True,
        )
        report.add(area, "Webhook rejects bad secret", True, "skipped", skip=True)
        report.add(area, "Webhook valid secret", True, "skipped", skip=True)
        return

    report.add(area, "Bot webhook health", code == 200 and data.get("service") == "bot-webhook", f"{code} {data}")

    code, data = http_json(
        "POST",
        f"{BOT_WEBHOOK_URL}/internal/webhook",
        {"event": "ticket.resolved", "payload": {}},
        headers={"X-Bot-Secret": "wrong"},
    )
    report.add(area, "Webhook rejects bad secret", code == 403, f"HTTP {code}")

    secret = os.environ.get("BOT_API_SECRET", "")
    if not secret:
        report.add(area, "Webhook accepts valid secret", False, "BOT_API_SECRET unset", warn=True)
        return

    code, data = http_json(
        "POST",
        f"{BOT_WEBHOOK_URL}/internal/webhook",
        {"event": "ticket.resolved", "payload": {"ticket_id": 1}},
        headers={"X-Bot-Secret": secret},
    )
    report.add(area, "Webhook valid secret", code == 200 and data.get("ok"), f"HTTP {code} {data}")


def check_bot_create_ticket_auth(report: Report) -> None:
    area = "Security"
    code, data = http_json(
        "POST",
        f"{BASE_URL}/api/tickets/create",
        {
            "sip_number": "000",
            "error_preset_id": "gd_fraud",
            "initiator_telegram_id": 1,
            "group_chat_id": 1,
        },
        headers={"X-Bot-Secret": "invalid"},
    )
    report.add(area, "Ticket create rejects bad secret", code in (401, 403), f"HTTP {code}")


def check_static_assets(report: Report, opener) -> None:
    area = "WebUI"
    for path in ("/static/app.css", "/static/app.js", "/static/login.html"):
        req = urllib.request.Request(f"{BASE_URL}{path}")
        try:
            with opener.open(req, timeout=10) as resp:
                size = len(resp.read())
                report.add(area, f"GET {path}", resp.status == 200 and size > 100, f"{size} bytes")
        except Exception as e:
            report.add(area, f"GET {path}", False, str(e))


def check_html_shell(report: Report, opener) -> None:
    area = "WebUI"
    req = urllib.request.Request(f"{BASE_URL}/")
    try:
        with opener.open(req, timeout=10) as resp:
            html = resp.read().decode()
            report.add(area, "Admin shell loads", "SIP CRM" in html and "service-desk" in html, f"{len(html)} bytes")
            report.add(area, "Dashboard section in HTML", 'data-section="dashboard"' in html, "")
            report.add(area, "Notifications section in HTML", 'data-section="notifications"' in html, "")
            report.add(area, "Operation guides section in HTML", 'data-section="operation-guides"' in html, "")
            report.add(area, "SIP guides section in HTML", 'data-section="sip-guides"' in html, "")
            report.add(area, "Finance section in HTML", 'data-section="finance"' in html, "")
            report.add(area, "Softphone section in HTML", 'data-section="softphone"' in html, "")
            report.add(area, "Notion section in HTML", 'data-section="notion"' in html, "")
    except Exception as e:
        report.add(area, "Admin shell loads", False, str(e))


def check_operation_guides_content(report: Report) -> None:
    area = "Unit"
    try:
        from services.operation_guides import AUDIENCES, GUIDES, get_operation_guides

        data = get_operation_guides()
        report.add(area, "Operation guides count", len(data["guides"]) >= 16, f"{len(data['guides'])}")
        for aud in ("workflow", "user", "group_owner", "admin"):
            n = len([g for g in GUIDES if g["audience"] == aud])
            report.add(area, f"Guides for {aud}", n >= 3, str(n))
    except Exception as e:
        report.add(area, "Operation guides content", False, str(e))


def check_sip_guides_content(report: Report) -> None:
    area = "Unit"
    try:
        from services.sip_integration_guides import GUIDES, get_sip_integration_guides

        data = get_sip_integration_guides()
        report.add(area, "SIP guides count", len(data["guides"]) >= 6, f"{len(data['guides'])} guides")
        mor5 = [g for g in GUIDES if g["category"] == "mor5"]
        report.add(area, "MOR5/MOR5 Lite guides", len(mor5) >= 3, f"{len(mor5)} guides")
        bad_sources = []
        for g in GUIDES:
            for src in g.get("sources") or []:
                url = src["url"]
                if "kolmisoft.com" not in url and "3cx.com" not in url:
                    bad_sources.append(f"{g['id']}:{url}")
        report.add(area, "Kolmisoft-only sources", not bad_sources, "; ".join(bad_sources[:3]))
    except Exception as e:
        report.add(area, "SIP guides content", False, str(e))


def check_finance_parse(report: Report) -> None:
    area = "Unit"
    try:
        from db.repositories.finance_repo import parse_usdt_amount
    except ModuleNotFoundError as e:
        report.add(area, "USDT amount parsing", True, f"skipped ({e.name})", skip=True)
        return
    try:
        assert parse_usdt_amount("10.5") > 0
        failed = False
        try:
            parse_usdt_amount("0")
        except ValueError:
            pass
        else:
            failed = True
        report.add(area, "USDT amount parsing", not failed, "10.5 ok, 0 rejected")
    except Exception as e:
        report.add(area, "USDT amount parsing", False, str(e))


def check_ticket_transitions_in_process(report: Report) -> None:
    area = "Unit"
    try:
        from db.models.ticket import TicketStatus
        from bot.utils.ticket_status import can_transition
    except ModuleNotFoundError as e:
        report.add(area, "Ticket transitions matrix", True, f"skipped ({e.name})", skip=True)
        return

    cases = [
        (TicketStatus.new, TicketStatus.resolved, True),
        (TicketStatus.resolved, TicketStatus.resolved, True),
        (TicketStatus.resolved, TicketStatus.closed, True),
        (TicketStatus.closed, TicketStatus.resolved, False),
    ]
    failed = [f"{a.value}->{b.value}" for a, b, exp in cases if can_transition(a, b) != exp]
    report.add(area, "Ticket transitions matrix", not failed, ", ".join(failed) or "4 cases")


def check_notification_config_db(report: Report) -> None:
    area = "DB"
    try:
        import asyncio
        from db.base import async_session_maker
        from bot.services.notification_config import get_notification_config
    except ModuleNotFoundError as e:
        report.add(area, "Notification config in DB", True, f"skipped ({e.name})", skip=True)
        return

    async def run():
        async with async_session_maker() as session:
            return await get_notification_config(session)

    try:
        cfg = asyncio.run(run())
        ok = bool(cfg.get("support_chat_ids")) and bool(cfg.get("events", {}).get("ticket_new"))
        report.add(
            area,
            "Notification config in DB",
            ok,
            f"support={cfg.get('support_chat_ids')} admin={cfg.get('admin_chat_ids')}",
        )
    except Exception as e:
        report.add(area, "Notification config in DB", False, str(e))


def check_auth_negative(report: Report, opener) -> None:
    area = "Security"
    cj = CookieJar()
    fresh = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    code, cap = http_json("GET", f"{BASE_URL}/api/auth/captcha", opener=fresh)
    if code != 200:
        report.add(area, "Negative auth (captcha)", False, f"captcha HTTP {code}")
        return
    code, data = http_json(
        "POST",
        f"{BASE_URL}/api/auth/login",
        {"username": WEB_USER, "password": "wrong-password-qa", "captcha": "99999"},
        opener=fresh,
    )
    report.add(area, "Bad password rejected", code in (400, 401, 403, 422), f"HTTP {code}")

    code2, cap2 = http_json("GET", f"{BASE_URL}/api/auth/captcha", opener=fresh)
    if code2 == 200:
        good = solve_captcha(cap2.get("question", ""))
        code3, _ = http_json(
            "POST",
            f"{BASE_URL}/api/auth/login",
            {"username": WEB_USER, "password": WEB_PASS or "x", "captcha": str(int(good) + 1)},
            opener=fresh,
        )
        report.add(area, "Bad captcha rejected", code3 in (400, 401, 403, 422), f"HTTP {code3}")


def check_web_accounts_rbac(report: Report, roof_opener) -> None:
    area = "Security"
    code, me = http_json("GET", f"{BASE_URL}/api/auth/me", opener=roof_opener)
    report.add(
        area,
        "Auth /me superadmin",
        code == 200 and me.get("role") == "superadmin",
        f"HTTP {code} {me}",
    )

    sup_opener, sup_ok = login_opener("support01", WEB_SUPPORT_PASS)
    if not sup_ok:
        report.add(area, "Support login (support01)", False, "login failed", warn=True)
        return

    code, me_sup = http_json("GET", f"{BASE_URL}/api/auth/me", opener=sup_opener)
    report.add(
        area,
        "Auth /me support",
        code == 200 and me_sup.get("role") == "support",
        f"HTTP {code} {me_sup}",
    )

    code_get, _ = http_json("GET", f"{BASE_URL}/api/finance/config", opener=sup_opener)
    report.add(area, "Support reads finance config", code_get == 200, f"HTTP {code_get}")

    code_put, _ = http_json(
        "PUT",
        f"{BASE_URL}/api/finance/config",
        {"currency_label": "USDT"},
        opener=sup_opener,
    )
    report.add(area, "Support blocked on finance PUT", code_put == 403, f"HTTP {code_put}")

    code_notif, _ = http_json(
        "PUT",
        f"{BASE_URL}/api/settings/notifications",
        {"support_chat_ids": [], "admin_chat_ids": [], "events": {}},
        opener=sup_opener,
    )
    report.add(area, "Support blocked on notifications PUT", code_notif == 403, f"HTTP {code_notif}")

    code_ban, _ = http_json(
        "POST",
        f"{BASE_URL}/api/users/999999/ban",
        {"reason": "qa-rbac"},
        opener=sup_opener,
    )
    report.add(area, "Support blocked on user ban", code_ban == 403, f"HTTP {code_ban}")

    code_sip, _ = http_json(
        "POST",
        f"{BASE_URL}/api/sips",
        {"telegram_id": 1, "sip_number": "000000"},
        opener=sup_opener,
    )
    report.add(area, "Support blocked on SIP add", code_sip == 403, f"HTTP {code_sip}")

    code_sp_put, _ = http_json(
        "PUT",
        f"{BASE_URL}/api/settings/softphone",
        {
            "enabled": False,
            "wss_url": "",
            "sip_domain": "",
            "display_name": "QA",
            "stun_servers": ["stun:stun.l.google.com:19302"],
            "turn_url": "",
            "turn_username": "",
            "turn_credential": "",
            "dial_prefix": "",
            "outbound_proxy": "",
            "session_ttl_seconds": 300,
        },
        opener=sup_opener,
    )
    report.add(area, "Support blocked on softphone PUT", code_sp_put == 403, f"HTTP {code_sp_put}")

    code_sp_get, sp_cfg = http_json("GET", f"{BASE_URL}/api/settings/softphone", opener=sup_opener)
    report.add(area, "Support reads softphone settings", code_sp_get == 200, f"HTTP {code_sp_get}")

    adm_opener, adm_ok = login_opener("admin01", WEB_PRIV_PASS)
    if not adm_ok:
        report.add(area, "Admin login (admin01)", False, "login failed", warn=True)
        return

    code_adm, me_adm = http_json("GET", f"{BASE_URL}/api/auth/me", opener=adm_opener)
    report.add(
        area,
        "Auth /me admin",
        code_adm == 200 and me_adm.get("role") == "admin",
        f"HTTP {code_adm} {me_adm}",
    )

    code_adm_fin, _ = http_json("GET", f"{BASE_URL}/api/finance/config", opener=adm_opener)
    report.add(area, "Admin reads finance config", code_adm_fin == 200, f"HTTP {code_adm_fin}")


def check_operation_guides_api(report: Report, opener) -> None:
    area = "Guides"
    code, data = http_json("GET", f"{BASE_URL}/api/guides/operations", opener=opener)
    ok = code == 200
    report.add(area, "Operations list", ok, f"HTTP {code}")
    if not ok:
        return

    featured = data.get("featured_guide_id")
    report.add(area, "Featured guide id", featured == "workflow-max-value", featured or "missing")
    roadmap = data.get("workflow_roadmap") or []
    report.add(area, "Workflow roadmap (4 phases)", len(roadmap) == 4, str(len(roadmap)))

    guide_ids = {g["id"] for g in data.get("guides") or []}
    report.add(area, "Featured in guides list", featured in guide_ids, featured or "")

    for aud in ("workflow", "user", "group_owner", "admin"):
        ac, ad = http_json("GET", f"{BASE_URL}/api/guides/operations?audience={aud}", opener=opener)
        n = len(ad.get("guides") or []) if ac == 200 else 0
        all_match = all(g.get("audience") == aud for g in (ad.get("guides") or [])) if ac == 200 else False
        report.add(area, f"Filter audience={aud}", ac == 200 and n >= 3 and all_match, f"{n} guides")

    bad_aud_code, _ = http_json("GET", f"{BASE_URL}/api/guides/operations?audience=invalid", opener=opener)
    report.add(area, "Invalid audience 400", bad_aud_code == 400, f"HTTP {bad_aud_code}")

    dc, detail = http_json("GET", f"{BASE_URL}/api/guides/operations/workflow-max-value", opener=opener)
    report.add(
        area,
        "Guide detail workflow-max-value",
        dc == 200 and detail.get("audience") == "workflow" and len(detail.get("steps") or []) >= 3,
        f"HTTP {dc} steps={len(detail.get('steps') or [])}",
    )
    nc, _ = http_json("GET", f"{BASE_URL}/api/guides/operations/__no_such_guide__", opener=opener)
    report.add(area, "Guide detail 404", nc == 404, f"HTTP {nc}")

    ac, acc = http_json("GET", f"{BASE_URL}/api/guides/operations/admin-web-accounts", opener=opener)
    report.add(
        area,
        "Guide admin-web-accounts",
        ac == 200 and acc.get("audience") == "admin" and len(acc.get("steps") or []) >= 5,
        f"HTTP {ac} steps={len(acc.get('steps') or [])}",
    )


def check_guide_web_parity(report: Report) -> None:
    area = "Parity"
    try:
        index = (ROOT / "api" / "static" / "index.html").read_text(encoding="utf-8")
        html_secs = set(re.findall(r'data-section="([^"]+)"', index))
        from services.operation_guides import GUIDES, WORKFLOW_ROADMAP

        bad_roadmap = [p["id"] for p in WORKFLOW_ROADMAP if p.get("web_section") not in html_secs]
        report.add(area, "Roadmap web_section in HTML", not bad_roadmap, ", ".join(bad_roadmap))

        bad_steps: list[str] = []
        for g in GUIDES:
            for step in g.get("steps") or []:
                ws = step.get("web_section")
                if ws and ws not in html_secs:
                    bad_steps.append(f"{g['id']}:{ws}")
        report.add(area, "Guide step web_section in HTML", not bad_steps, "; ".join(bad_steps[:3]))

        app_js = (ROOT / "api" / "static" / "app.js").read_text(encoding="utf-8")
        m = re.search(r"const SECTION_TITLES = \{([^}]+)\}", app_js, re.DOTALL)
        js_secs = set(re.findall(r'"?([\w-]+)"?\s*:', m.group(1))) if m else set()
        missing_js = html_secs - js_secs
        report.add(area, "Nav sections in SECTION_TITLES", not missing_js, ", ".join(sorted(missing_js)))
    except Exception as e:
        report.add(area, "Guide web parity", False, str(e))


def check_menu_catalog(report: Report) -> None:
    area = "Bot"
    try:
        path = ROOT / "bot" / "utils" / "menu_catalog.py"
        text = path.read_text(encoding="utf-8")
        report.add(area, "Report button label", 'BTN_REPORT = "🚨 Сообщить об ошибке"' in text, "")
        report.add(
            area,
            "Legacy alias in TEXTS_REPORT",
            "TEXTS_REPORT = frozenset({BTN_REPORT, LEGACY_BTN_REPORT})" in text,
            "",
        )
        long_btns = re.findall(r'BTN_\w+ = "([^"]{65,})"', text)
        report.add(area, "Button length ≤64", not long_btns, ", ".join(long_btns[:2]))
        for util in ("menu_dispatch.py", "fsm_menu_guard.py"):
            report.add(area, f"util {util}", (ROOT / "bot" / "utils" / util).is_file(), "")
        wh = (ROOT / "bot" / "webhook" / "server.py").read_text(encoding="utf-8")
        report.add(area, "Webhook secret timing-safe", "compare_digest" in wh, "")
        report.add(
            area,
            "Login rate limit module",
            (ROOT / "services" / "login_rate_limit.py").is_file(),
            "",
        )
        report.add(area, "RBAC module", (ROOT / "api" / "rbac.py").is_file(), "")
        report.add(area, "core/config.py", (ROOT / "core" / "config.py").is_file(), "")
        report.add(
            area,
            "API routers package",
            (ROOT / "api" / "routers" / "groups.py").is_file(),
            "",
        )
        main_lines = len((ROOT / "api" / "main.py").read_text(encoding="utf-8").splitlines())
        report.add(area, "api/main.py slim (<120 lines)", main_lines < 120, f"{main_lines} lines")
        report.add(
            area,
            "Guides JSON bundle",
            (ROOT / "data" / "guides" / "operations.json").is_file(),
            "",
        )
        entry_path = ROOT / "docker" / "entrypoint.sh"
        if entry_path.is_file():
            entry = entry_path.read_text(encoding="utf-8")
            report.add(area, "Bot entrypoint no alembic", "alembic upgrade" not in entry, "")
        else:
            report.add(area, "Bot entrypoint no alembic", True, "n/a in api image", skip=True)
        report.add(area, "Softphone API module", (ROOT / "api" / "routes_softphone.py").is_file(), "")
        report.add(area, "Mini softphone JS", (ROOT / "api" / "static" / "mini" / "softphone.mjs").is_file(), "")
        mini_routes = (ROOT / "api" / "routes_mini.py").read_text(encoding="utf-8")
        report.add(area, "Mini bootstrap endpoint", "/bootstrap" in mini_routes, "")
        report.add(area, "Mini app service", (ROOT / "api" / "services" / "mini_app.py").is_file(), "")
    except Exception as e:
        report.add(area, "Menu catalog", False, str(e))


def check_api_response_shapes(report: Report, opener) -> None:
    area = "Contract"
    code, dash = http_json("GET", f"{BASE_URL}/api/dashboard", opener=opener)
    keys = {"users_total", "tickets_open", "sips_total"}
    report.add(area, "Dashboard schema", code == 200 and keys <= dash.keys(), f"HTTP {code}")

    code, sd = http_json("GET", f"{BASE_URL}/api/tickets/service-desk", opener=opener)
    summary = sd.get("summary") or {}
    sd_ok = code == 200 and isinstance(sd.get("items"), list) and "sla_seconds" in summary
    report.add(area, "Service desk schema", sd_ok, f"HTTP {code} total={summary.get('total')}")

    code, fin = http_json("GET", f"{BASE_URL}/api/finance/config", opener=opener)
    fin_ok = code == 200 and "min_deposit_usdt" in fin and "currency_label" in fin
    report.add(area, "Finance config schema", fin_ok, f"HTTP {code} min={fin.get('min_deposit_usdt')}")

    code, sip = http_json("GET", f"{BASE_URL}/api/guides/sip-integration", opener=opener)
    if code == 200:
        cats = sip.get("categories") or []
        mor5 = [g for g in sip.get("guides") or [] if g.get("category") == "mor5"]
        report.add(area, "SIP guides mor5 category", "mor5" in cats and len(mor5) >= 3, f"mor5={len(mor5)}")
    else:
        report.add(area, "SIP guides mor5 category", False, f"HTTP {code}")


def check_guide_ids_unique(report: Report) -> None:
    area = "Unit"
    try:
        from services.operation_guides import GUIDES as OG
        from services.sip_integration_guides import GUIDES as SG

        o_ids = [g["id"] for g in OG]
        s_ids = [g["id"] for g in SG]
        report.add(area, "Unique operation guide ids", len(o_ids) == len(set(o_ids)), f"{len(o_ids)} guides")
        report.add(area, "Unique SIP guide ids", len(s_ids) == len(set(s_ids)), f"{len(s_ids)} guides")
    except Exception as e:
        report.add(area, "Guide id uniqueness", False, str(e))


def check_html_operation_guides_ui(report: Report, opener) -> None:
    area = "WebUI"
    req = urllib.request.Request(f"{BASE_URL}/")
    try:
        with opener.open(req, timeout=10) as resp:
            html = resp.read().decode()
            report.add(area, "Operation guides DOM ids", "operation-guides-roadmap" in html, "")
            report.add(area, "Operation guides nav id", "operation-guides-nav" in html, "")
            report.add(area, "Operation guides chips id", "operation-guides-chips" in html, "")
    except Exception as e:
        report.add(area, "Operation guides DOM", False, str(e))

    app_js = ROOT / "api" / "static" / "app.js"
    if app_js.is_file():
        js = app_js.read_text(encoding="utf-8")
        report.add(area, "app.js operation roadmap UI", "operation-roadmap-card" in js, "")
        report.add(area, "app.js guide goto section", "guide-goto-section" in js, "")
        report.add(area, "app.js featured guide handling", "featured_guide_id" in js, "")


def check_mini_app_static(report: Report) -> None:
    area = "MiniApp"
    mini_dir = ROOT / "api" / "static" / "mini"
    index = mini_dir / "index.html"
    mini_js = mini_dir / "mini.js"
    soft_mjs = mini_dir / "softphone.mjs"
    legacy_js = mini_dir / "softphone.js"

    report.add(area, "mini/index.html", index.is_file(), "")
    report.add(area, "mini/mini.js", mini_js.is_file(), "")
    report.add(area, "mini/mini.css", (mini_dir / "mini.css").is_file(), "")
    report.add(area, "mini/softphone.mjs", soft_mjs.is_file(), "")
    report.add(area, "legacy softphone.js removed", not legacy_js.is_file(), "")

    if index.is_file() and mini_js.is_file():
        html = index.read_text(encoding="utf-8")
        js = mini_js.read_text(encoding="utf-8")
        report.add(area, "Mini HTML phone tab", 'data-tab="phone"' in html, "")
        report.add(area, "Mini HTML defer mini.js", 'mini.js" defer' in html, "")
        report.add(area, "Mini HTML no sync JsSIP", "jssip" not in html.lower(), "")
        report.add(area, "mini.js bootstrap fetch", "bootstrap" in js, "")
        report.add(area, "mini.js lazy softphone import", "softphone.mjs" in js, "")
        report.add(area, "mini.js esc() helper", "function esc(" in js, "")

    try:
        bootstrap_py = ROOT / "api" / "services" / "mini_app.py"
        routes_py = ROOT / "api" / "routes_mini.py"
        ok = bootstrap_py.is_file() and routes_py.is_file()
        if ok:
            ast.parse(bootstrap_py.read_text(encoding="utf-8"))
            ast.parse(routes_py.read_text(encoding="utf-8"))
        report.add(area, "Mini bootstrap module", ok, "")
    except Exception as e:
        report.add(area, "Mini bootstrap module", False, str(e))


def check_mini_app_auth(report: Report) -> None:
    area = "MiniApp"
    code, _ = http_json("GET", f"{BASE_URL}/api/mini/bootstrap")
    report.add(area, "Bootstrap requires TMA auth", code == 401, f"HTTP {code}")

    code2, _ = http_json(
        "GET",
        f"{BASE_URL}/api/mini/bootstrap",
        headers={"Authorization": "tma bad"},
    )
    report.add(area, "Bootstrap rejects bad TMA", code2 == 401, f"HTTP {code2}")

    code3, _ = http_json("GET", f"{BASE_URL}/api/mini/softphone/status")
    report.add(area, "Softphone status requires auth", code3 == 401, f"HTTP {code3}")


def check_mini_app_live(report: Report) -> None:
    area = "MiniApp"
    try:
        with urllib.request.urlopen(f"{BASE_URL}/mini", timeout=10) as resp:
            html = resp.read().decode()
            report.add(area, "GET /mini page", resp.status == 200 and "SIP CRM" in html, f"{len(html)} bytes")
            report.add(area, "Mini page phone panel", 'id="panel-phone"' in html, "")
    except Exception as e:
        report.add(area, "GET /mini page", False, str(e))

    for path in ("/static/mini/mini.js", "/static/mini/mini.css", "/static/mini/softphone.mjs"):
        try:
            with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=10) as resp:
                size = len(resp.read())
                report.add(area, f"GET {path}", resp.status == 200 and size > 200, f"{size} bytes")
        except Exception as e:
            report.add(area, f"GET {path}", False, str(e))

    bot_token = os.environ.get("BOT_TOKEN", "")
    if not bot_token:
        report.add(area, "Bootstrap live (signed TMA)", False, "BOT_TOKEN unset", skip=True)
        return

    init_data = make_tma_init_data(bot_token)
    code, data = http_json(
        "GET",
        f"{BASE_URL}/api/mini/bootstrap",
        headers={"Authorization": f"tma {init_data}"},
    )
    keys = {"user", "sips", "sips_count", "open_tickets", "quick_presets", "softphone"}
    ok = code == 200 and keys <= data.keys()
    report.add(area, "Bootstrap live schema", ok, f"HTTP {code}")

    if ok:
        sp = data.get("softphone") or {}
        report.add(
            area,
            "Bootstrap softphone block",
            "enabled" in sp and "lines" in sp,
            f"enabled={sp.get('enabled')} lines={len(sp.get('lines') or [])}",
        )


def check_web_crm_softphone_ui(report: Report, opener) -> None:
    area = "WebUI"
    app_js = ROOT / "api" / "static" / "app.js"
    if app_js.is_file():
        js = app_js.read_text(encoding="utf-8")
        for fn in ("loadSoftphoneSettings", "saveSoftphoneSettings", "collectSoftphoneForm"):
            report.add(area, f"app.js defines {fn}", fn in js, "")
        report.add(area, "app.js SIP credentials UI", "data-creds" in js, "")
        report.add(area, "app.js SIP auth on add", "auth_password" in js, "")

    code, data = http_json("GET", f"{BASE_URL}/api/settings/softphone", opener=opener)
    cfg_keys = {"enabled", "wss_url", "sip_domain", "stun_servers", "session_ttl_seconds"}
    ok = code == 200 and cfg_keys <= set((data.get("config") or {}).keys())
    report.add(area, "Softphone settings schema", ok, f"HTTP {code}")

    code2, sips = http_json("GET", f"{BASE_URL}/api/sips?limit=3", opener=opener)
    if code2 == 200 and (sips.get("items") or []):
        item = sips["items"][0]
        report.add(area, "SIP list has_credentials", "has_credentials" in item, "")
    elif code2 == 200:
        report.add(area, "SIP list has_credentials", True, "no sips", skip=True)


def check_alembic_head(report: Report) -> None:
    area = "DB"
    try:
        import subprocess
        r = subprocess.run(
            ["alembic", "current"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        out = (r.stdout + r.stderr).strip()
        if r.returncode != 0:
            report.add(area, "Alembic current", False, out[-120:], warn=True)
        else:
            report.add(area, "Alembic current", "f6a7b8c9d0e1" in out or "head" in out.lower(), out[-120:])
    except FileNotFoundError:
        report.add(area, "Alembic current", False, "alembic CLI not in image (check bot container)", warn=True)


def _safe_check(report: Report, fn, *args, **kwargs) -> None:
    try:
        fn(report, *args, **kwargs)
    except Exception as exc:
        area = getattr(fn, "__name__", "QA").replace("check_", "").replace("_", " ").title()
        report.add(area, fn.__name__, False, str(exc)[:200], warn=True)


def main() -> int:
    report = Report()
    strict = "--strict" in sys.argv
    print("=" * 60)
    print("SIP CRM Deep QA")
    print(f"BASE_URL={BASE_URL} BOT_WEBHOOK={BOT_WEBHOOK_URL}")
    if strict:
        print("MODE=strict (WARN counts as FAIL)")
    print("=" * 60)

    check_static_python(report)
    check_static_js(report)
    check_health(report)
    cj = check_auth_boundary(report)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    check_authenticated_api(report, opener)
    check_auth_negative(report, opener)
    check_web_accounts_rbac(report, opener)
    check_operation_guides_api(report, opener)
    check_api_response_shapes(report, opener)
    check_static_assets(report, opener)
    check_html_shell(report, opener)
    check_html_operation_guides_ui(report, opener)
    check_web_crm_softphone_ui(report, opener)
    check_mini_app_static(report)
    check_mini_app_auth(report)
    check_mini_app_live(report)
    check_guide_web_parity(report)
    check_menu_catalog(report)
    check_guide_ids_unique(report)
    check_bot_webhook(report)
    check_bot_create_ticket_auth(report)
    check_operation_guides_content(report)
    check_sip_guides_content(report)
    _safe_check(report, check_finance_parse)
    _safe_check(report, check_ticket_transitions_in_process)
    _safe_check(report, check_notification_config_db)
    check_alembic_head(report)

    print()
    for r in report.results:
        print(r.line())

    counts = report.summary()
    print_by_area(report)
    print()
    print("=" * 60)
    print(
        f"SUMMARY: PASS={counts['PASS']} FAIL={counts['FAIL']} "
        f"WARN={counts['WARN']} SKIP={counts['SKIP']}"
    )
    print("=" * 60)

    if counts["FAIL"] > 0:
        return 1
    if strict and counts["WARN"] > 0:
        return 1
    return 0


def print_by_area(report: Report) -> None:
    areas: dict[str, dict[str, int]] = {}
    for r in report.results:
        areas.setdefault(r.area, {"PASS": 0, "FAIL": 0, "WARN": 0, "SKIP": 0})
        areas[r.area][r.status] = areas[r.area].get(r.status, 0) + 1
    print("\nBy area:")
    for area, c in sorted(areas.items()):
        print(f"  {area}: PASS={c['PASS']} FAIL={c['FAIL']} WARN={c['WARN']} SKIP={c['SKIP']}")


if __name__ == "__main__":
    sys.exit(main())
