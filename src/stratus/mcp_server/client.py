"""Async httpx client wrapper for the memory HTTP API."""

from __future__ import annotations

import httpx


class MemoryClient:
    def __init__(self, base_url: str | None = None) -> None:
        if base_url is None:
            from stratus.hooks._common import get_api_url

            base_url = get_api_url()
        self._base_url = base_url
        self._client = httpx.AsyncClient(base_url=base_url, timeout=10.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def health(self) -> dict:
        resp = await self._client.get("/health")
        resp.raise_for_status()
        return resp.json()

    async def search(
        self,
        query: str,
        *,
        limit: int = 20,
        type: str | None = None,
        scope: str | None = None,
        project: str | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
        offset: int = 0,
    ) -> dict:
        params: dict = {"query": query, "limit": limit, "offset": offset}
        if type:
            params["type"] = type
        if scope:
            params["scope"] = scope
        if project:
            params["project"] = project
        if date_start:
            params["date_start"] = date_start
        if date_end:
            params["date_end"] = date_end

        resp = await self._client.get("/api/search", params=params)
        resp.raise_for_status()
        return resp.json()

    async def timeline(
        self,
        anchor_id: int | None = None,
        query: str | None = None,
        depth_before: int = 10,
        depth_after: int = 10,
        project: str | None = None,
    ) -> dict:
        params: dict = {"depth_before": depth_before, "depth_after": depth_after}
        if anchor_id is not None:
            params["anchor_id"] = anchor_id
        if query:
            params["query"] = query
        if project:
            params["project"] = project

        resp = await self._client.get("/api/timeline", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_observations(self, ids: list[int]) -> dict:
        resp = await self._client.post("/api/observations/batch", json={"ids": ids})
        resp.raise_for_status()
        return resp.json()

    async def save_memory(self, **kwargs) -> dict:
        resp = await self._client.post("/api/memory/save", json=kwargs)
        resp.raise_for_status()
        return resp.json()

    async def delivery_dispatch(self) -> dict:
        resp = await self._client.get("/api/delivery/dispatch")
        resp.raise_for_status()
        return resp.json()
