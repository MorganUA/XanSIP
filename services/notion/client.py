"""Асинхронный HTTP-клиент Notion API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from bot.config import settings
from services.notion.errors import NotionError, NotionNotConfiguredError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 20.0


class NotionClient:
    BASE_URL = "https://api.notion.com/v1"

    def __init__(
        self,
        *,
        token: str | None = None,
        api_version: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.token = (token if token is not None else settings.notion_api_token).strip()
        self.api_version = api_version or settings.notion_api_version
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.token)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": self.api_version,
            "Content-Type": "application/json",
        }

    def _ensure_token(self) -> None:
        if not self.is_configured():
            raise NotionNotConfiguredError()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_token()
        url = f"{self.BASE_URL}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(
                    method,
                    url,
                    headers=self._headers(),
                    json=json,
                    params=params,
                )
            except httpx.HTTPError as exc:
                logger.exception("Notion HTTP error %s %s", method, path)
                raise NotionError(str(exc), status_code=0, code="http_error") from exc

        if response.status_code >= 400:
            detail = response.text
            code = None
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    detail = payload.get("message") or detail
                    code = payload.get("code")
            except Exception:
                payload = None
            raise NotionError(
                detail or f"Notion HTTP {response.status_code}",
                status_code=response.status_code,
                code=code,
            )

        if not response.content:
            return {}
        data = response.json()
        return data if isinstance(data, dict) else {"data": data}

    async def get_me(self) -> dict[str, Any]:
        return await self._request("GET", "/users/me")

    async def search(
        self,
        *,
        query: str = "",
        filter_obj: dict[str, Any] | None = None,
        sort: dict[str, Any] | None = None,
        start_cursor: str | None = None,
        page_size: int = 20,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"page_size": min(page_size, 100)}
        if query:
            body["query"] = query
        if filter_obj:
            body["filter"] = filter_obj
        if sort:
            body["sort"] = sort
        if start_cursor:
            body["start_cursor"] = start_cursor
        return await self._request("POST", "/search", json=body)

    async def get_database(self, database_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/databases/{database_id}")

    async def create_database(
        self,
        *,
        parent_page_id: str,
        title: str,
        properties: dict[str, Any],
        icon_emoji: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "title": [{"type": "text", "text": {"content": title[:100]}}],
            "properties": properties,
        }
        if icon_emoji:
            body["icon"] = {"type": "emoji", "emoji": icon_emoji}
        return await self._request("POST", "/databases", json=body)

    async def query_database(
        self,
        database_id: str,
        *,
        filter_obj: dict[str, Any] | None = None,
        sorts: list[dict[str, Any]] | None = None,
        start_cursor: str | None = None,
        page_size: int = 20,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"page_size": min(page_size, 100)}
        if filter_obj:
            body["filter"] = filter_obj
        if sorts:
            body["sorts"] = sorts
        if start_cursor:
            body["start_cursor"] = start_cursor
        return await self._request("POST", f"/databases/{database_id}/query", json=body)

    async def get_page(self, page_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/pages/{page_id}")

    async def create_page(
        self,
        *,
        parent: dict[str, Any],
        properties: dict[str, Any],
        children: list[dict[str, Any]] | None = None,
        icon: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"parent": parent, "properties": properties}
        if children:
            body["children"] = children
        if icon:
            body["icon"] = icon
        return await self._request("POST", "/pages", json=body)

    async def update_page(
        self,
        page_id: str,
        *,
        properties: dict[str, Any] | None = None,
        archived: bool | None = None,
        icon: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if properties is not None:
            body["properties"] = properties
        if archived is not None:
            body["archived"] = archived
        if icon is not None:
            body["icon"] = icon
        return await self._request("PATCH", f"/pages/{page_id}", json=body)

    async def append_blocks(self, block_id: str, children: list[dict[str, Any]]) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            f"/blocks/{block_id}/children",
            json={"children": children},
        )

    async def get_block_children(
        self,
        block_id: str,
        *,
        start_cursor: str | None = None,
        page_size: int = 50,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"page_size": min(page_size, 100)}
        if start_cursor:
            params["start_cursor"] = start_cursor
        return await self._request("GET", f"/blocks/{block_id}/children", params=params)

    async def create_database_page(
        self,
        database_id: str,
        properties: dict[str, Any],
        *,
        children: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return await self.create_page(
            parent={"database_id": database_id},
            properties=properties,
            children=children,
        )


def get_notion_client() -> NotionClient:
    return NotionClient()
