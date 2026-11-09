"""Minimal OpenSubtitles.com REST API client."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import aiohttp

API_BASE = "https://api.opensubtitles.com/api/v1"
USER_AGENT = "Subveil/0.1.0 (+https://github.com/Kgym-Hina/Subveil)"
TIMEOUT = aiohttp.ClientTimeout(total=20)


def _normalize(title: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", title.lower()).split())


class OpenSubtitlesError(Exception):
    """Raised when the OpenSubtitles API returns an error."""


@dataclass
class Candidate:
    """A subtitle that can be selected."""

    id: str
    label: str
    source: str
    file_id: int | None = None
    language: str | None = None
    title_match: bool = False
    downloads: int = 0


class OpenSubtitlesClient:
    """Searches and downloads subtitles from OpenSubtitles.com."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
        username: str = "",
        password: str = "",
    ) -> None:
        self._session = session
        self._api_key = api_key
        self._username = username
        self._password = password
        self._base = API_BASE
        self._token: str | None = None

    def _headers(self) -> dict[str, str]:
        headers = {
            "Api-Key": self._api_key,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        async with self._session.request(
            method, f"{self._base}{path}", headers=self._headers(), timeout=TIMEOUT, **kwargs
        ) as resp:
            try:
                data = await resp.json(content_type=None)
            except ValueError:
                data = None
            if not isinstance(data, dict):
                data = {}
            if resp.status >= 400:
                msg = data.get("message") or data.get("errors") or resp.reason
                raise OpenSubtitlesError(f"HTTP {resp.status}: {msg}")
            return data

    async def login(self) -> None:
        if not self._username or self._token:
            return
        data = await self._request(
            "POST", "/login", json={"username": self._username, "password": self._password}
        )
        self._token = data.get("token")
        if base := data.get("base_url"):
            self._base = f"https://{base}/api/v1"

    async def search(
        self,
        query: str,
        languages: list[str],
        season: int | None = None,
        episode: int | None = None,
    ) -> list[Candidate]:
        params = {
            "query": query.strip().lower(),
            "languages": ",".join(sorted(languages)),
            "order_by": "download_count",
        }
        if season is not None and episode is not None:
            params.update(
                type="episode", season_number=str(season), episode_number=str(episode)
            )
        data = await self._request("GET", "/subtitles", params=params)

        results: list[Candidate] = []
        for item in data.get("data", []):
            attrs = item.get("attributes") or {}
            files = attrs.get("files") or []
            if not files:
                continue
            file = files[0]
            lang = (attrs.get("language") or "?").lower()
            release = attrs.get("release") or file.get("file_name") or query
            feature = attrs.get("feature_details") or {}
            titles = {
                _normalize(feature.get(k) or "")
                for k in ("title", "movie_name", "parent_title")
            }
            notes = [f"↓{attrs.get('download_count', 0)}"]
            if attrs.get("hearing_impaired"):
                notes.append("HI")
            if attrs.get("machine_translated") or attrs.get("ai_translated"):
                notes.append("MT")
            results.append(
                Candidate(
                    id=f"os:{file['file_id']}",
                    label=f"[{lang}] {release} · {' · '.join(notes)}",
                    source="opensubtitles",
                    file_id=int(file["file_id"]),
                    language=lang,
                    title_match=_normalize(query) in titles,
                    downloads=int(attrs.get("download_count") or 0),
                )
            )
        order = {lang: i for i, lang in enumerate(languages)}
        # OpenSubtitles does fuzzy matching, so "Nocturne" also returns "Nocturnal Animals".
        results.sort(
            key=lambda c: (
                not c.title_match,
                order.get(c.language or "", len(order)),
                -c.downloads,
            )
        )
        return results

    async def download(self, file_id: int) -> tuple[str, bytes]:
        await self.login()
        try:
            data = await self._request("POST", "/download", json={"file_id": file_id})
        except OpenSubtitlesError as err:
            if "HTTP 401" not in str(err) or not self._username:
                raise
            self._token = None
            await self.login()
            data = await self._request("POST", "/download", json={"file_id": file_id})

        link = data.get("link")
        if not link:
            raise OpenSubtitlesError(data.get("message") or "download link missing")
        async with self._session.get(
            link, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}
        ) as resp:
            resp.raise_for_status()
            content = await resp.read()
        return data.get("file_name") or f"{file_id}.srt", content
