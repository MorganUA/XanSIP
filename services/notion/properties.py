"""Хелперы для свойств страниц Notion (properties payload)."""

from __future__ import annotations

from typing import Any


def title(text: str) -> dict[str, Any]:
    return {"title": [{"type": "text", "text": {"content": text[:2000]}}]}


def rich_text(text: str) -> dict[str, Any]:
    return {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]}


def number(value: int | float) -> dict[str, Any]:
    return {"number": value}


def checkbox(checked: bool) -> dict[str, Any]:
    return {"checkbox": checked}


def select(name: str) -> dict[str, Any]:
    return {"select": {"name": name}}


def multi_select(names: list[str]) -> dict[str, Any]:
    return {"multi_select": [{"name": n} for n in names]}


def date(start: str, end: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"start": start}
    if end:
        payload["end"] = end
    return {"date": payload}


def url(value: str) -> dict[str, Any]:
    return {"url": value}


def email(value: str) -> dict[str, Any]:
    return {"email": value}


def phone(value: str) -> dict[str, Any]:
    return {"phone_number": value}


def status(name: str) -> dict[str, Any]:
    return {"status": {"name": name}}


def paragraph_block(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": text[:2000]}}],
        },
    }


def heading_2_block(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": text[:2000]}}],
        },
    }
