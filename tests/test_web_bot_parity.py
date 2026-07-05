"""Parity: Web CRM sections, bot menu, operation guides cross-links."""
from __future__ import annotations

import re
from pathlib import Path

from services.operation_guides import GUIDES, WORKFLOW_ROADMAP

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "api" / "static" / "index.html"
APP_JS = ROOT / "api" / "static" / "app.js"
MENU_CATALOG = ROOT / "bot" / "utils" / "menu_catalog.py"


def _html_nav_sections() -> set[str]:
    text = INDEX_HTML.read_text(encoding="utf-8")
    return set(re.findall(r'data-section="([^"]+)"', text))


def _js_section_titles() -> set[str]:
    text = APP_JS.read_text(encoding="utf-8")
    m = re.search(r"const SECTION_TITLES = \{([^}]+)\}", text, re.DOTALL)
    assert m, "SECTION_TITLES not found"
    return set(re.findall(r'"?([\w-]+)"?\s*:', m.group(1)))


def test_html_nav_sections_have_js_titles():
    html_secs = _html_nav_sections()
    js_secs = _js_section_titles()
    missing_in_js = html_secs - js_secs
    assert not missing_in_js, f"nav sections without SECTION_TITLES: {missing_in_js}"


def test_workflow_roadmap_sections_in_html():
    html_secs = _html_nav_sections()
    for phase in WORKFLOW_ROADMAP:
        assert phase["web_section"] in html_secs, phase["id"]


def test_guide_web_sections_in_html():
    html_secs = _html_nav_sections()
    bad: list[str] = []
    for g in GUIDES:
        for step in g.get("steps") or []:
            ws = step.get("web_section")
            if ws and ws not in html_secs:
                bad.append(f"{g['id']}:{ws}")
    assert not bad, bad


def test_operation_guides_ui_hooks_in_html():
    text = INDEX_HTML.read_text(encoding="utf-8")
    for el_id in (
        "operation-guides",
        "operation-guides-roadmap",
        "operation-guides-nav",
        "operation-guides-chips",
        "operation-guides-search",
    ):
        assert el_id in text, el_id


def test_app_js_operation_guides_loader():
    text = APP_JS.read_text(encoding="utf-8")
    assert "loadOperationGuides" in text
    assert "operation-roadmap-card" in text
    assert "guide-goto-section" in text
    assert "featured_guide_id" in text


def test_report_button_primary_label():
    text = MENU_CATALOG.read_text(encoding="utf-8")
    assert 'BTN_REPORT = "🚨 Сообщить об ошибке"' in text
    assert "TEXTS_REPORT = frozenset({BTN_REPORT, LEGACY_BTN_REPORT})" in text


def test_sip_guides_section_in_html():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert 'data-section="sip-guides"' in text
    assert "sip-guides" in text


def test_softphone_section_in_html_and_js():
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'data-section="softphone"' in html
    js = APP_JS.read_text(encoding="utf-8")
    assert "softphone" in js
    assert "loadSoftphoneSettings" in js
    html_secs = _html_nav_sections()
    js_secs = _js_section_titles()
    assert "softphone" in html_secs
    assert "softphone" in js_secs
