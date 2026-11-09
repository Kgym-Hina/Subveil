"""HTTP client for the TV overlay app."""

from __future__ import annotations

from typing import Any

import aiohttp

TIMEOUT = aiohttp.ClientTimeout(total=10)


class TvClient:
    """Talks to the Subveil app running on the TV."""

    def __init__(self, session: aiohttp.ClientSession, host: str, port: int) -> None:
        self._session = session
        self._base = f"http://{host}:{port}"

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        async with self._session.request(
            method, f"{self._base}{path}", timeout=TIMEOUT, **kwargs
        ) as resp:
            data = await resp.json(content_type=None)
            if resp.status >= 400:
                raise aiohttp.ClientResponseError(
                    resp.request_info,
                    resp.history,
                    status=resp.status,
                    message=str((data or {}).get("error", resp.reason)),
                )
            return data or {}

    async def status(self) -> dict[str, Any]:
        return await self._request("GET", "/status")

    async def load_subtitle(self, name: str, data: bytes) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/subtitle",
            params={"name": name},
            data=data,
            headers={"Content-Type": "application/octet-stream"},
        )

    async def clear(self) -> dict[str, Any]:
        return await self._request("POST", "/clear")

    async def sync(self, position_ms: int, playing: bool, visible: bool = True) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/sync",
            json={"position_ms": position_ms, "playing": playing, "visible": visible},
        )

    async def set_offset(self, offset_ms: int, notify: bool = False) -> dict[str, Any]:
        params = {"notify": "1"} if notify else None
        return await self._request(
            "POST", "/offset", params=params, json={"offset_ms": offset_ms}
        )

    async def set_visible(self, visible: bool) -> dict[str, Any]:
        return await self._request("POST", "/visible", json={"visible": visible})

    async def set_text_size(self, px: float) -> dict[str, Any]:
        return await self._request("POST", "/style", json={"text_size_px": px})
