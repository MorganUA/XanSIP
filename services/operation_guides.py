"""Руководства по эксплуатации SIP CRM — данные в data/guides/operations.json."""

from __future__ import annotations

from typing import Any

from services.guides_loader import load_guide_bundle

_bundle = load_guide_bundle("operations")

AUDIENCES: dict[str, dict[str, str]] = _bundle["audiences"]
FEATURED_GUIDE_ID: str = _bundle["featured_guide_id"]
WORKFLOW_ROADMAP: list[dict[str, str]] = _bundle["workflow_roadmap"]
GUIDES: list[dict[str, Any]] = _bundle["guides"]
_DISCLAIMER: str = _bundle["disclaimer"]


def get_operation_guides(*, audience: str | None = None) -> dict[str, Any]:
    guides = list(GUIDES)
    if audience:
        guides = [g for g in guides if g["audience"] == audience]
    else:
        order = {"workflow": 0, "user": 1, "group_owner": 2, "admin": 3}
        guides.sort(key=lambda g: (order.get(g["audience"], 9), g["title"]))
    return {
        "disclaimer": _DISCLAIMER,
        "featured_guide_id": FEATURED_GUIDE_ID,
        "workflow_roadmap": WORKFLOW_ROADMAP,
        "audiences": AUDIENCES,
        "guides": guides,
    }


def get_guide_by_id(guide_id: str) -> dict[str, Any] | None:
    for g in GUIDES:
        if g["id"] == guide_id:
            return g
    return None


def guides_for_audience(audience: str) -> list[dict[str, Any]]:
    return [g for g in GUIDES if g["audience"] == audience]


def format_guide_html(guide: dict[str, Any]) -> str:
    aud = AUDIENCES.get(guide["audience"], {})
    lines = [
        f"<b>{guide['title']}</b>",
        f"<i>{aud.get('label', guide['audience'])}</i>",
        "",
        guide.get("summary", ""),
        "",
    ]
    for step in guide.get("steps") or []:
        lines.append(f"<b>{step['title']}</b>")
        lines.append(step["body"])
        if step.get("menu"):
            lines.append(f"→ {step['menu']}")
        if step.get("note"):
            lines.append(f"ℹ️ {step['note']}")
        lines.append("")
    return "\n".join(lines).strip()


def split_telegram_text(text: str, limit: int = 4000) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    current = ""
    for block in text.split("\n\n"):
        chunk = block + "\n\n"
        if len(current) + len(chunk) > limit and current:
            parts.append(current.strip())
            current = chunk
        else:
            current += chunk
    if current.strip():
        parts.append(current.strip())
    return parts or [text[:limit]]
