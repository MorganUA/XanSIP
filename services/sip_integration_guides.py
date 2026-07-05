"""Справочники по интеграции SIP — данные в data/guides/sip-integration.json."""

from __future__ import annotations

from typing import Any

from services.guides_loader import load_guide_bundle

_bundle = load_guide_bundle("sip-integration")

GUIDES: list[dict[str, Any]] = _bundle["guides"]
CATEGORIES: dict[str, dict[str, str]] = _bundle["categories"]
_DISCLAIMER: str = _bundle["disclaimer"]


def get_sip_integration_guides() -> dict[str, Any]:
    return {
        "disclaimer": _DISCLAIMER,
        "categories": CATEGORIES,
        "guides": GUIDES,
    }
