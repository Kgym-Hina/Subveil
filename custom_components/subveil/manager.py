"""Ties the media player, OpenSubtitles and the TV overlay together."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any

import aiohttp

from homeassistant.components.media_player import MediaPlayerState
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AUTO_SEARCH,
    CONF_LANGUAGES,
    CONF_MEDIA_PLAYER,
    CONF_OS_API_KEY,
    CONF_OS_PASSWORD,
    CONF_OS_USERNAME,
    DEFAULT_LANGUAGES,
    DOMAIN,
    MAX_CANDIDATES,
    STATUS_DOWNLOAD_FAILED,
    STATUS_DOWNLOADING,
    STATUS_FOUND,
    STATUS_IDLE,
    STATUS_INVALID_SUBTITLE,
    STATUS_LOADED,
    STATUS_NO_API_KEY,
    STATUS_NO_TITLE,
    STATUS_NOT_FOUND,
    STATUS_OFF,
    STATUS_PLAYING,
    STATUS_SEARCH_FAILED,
    STATUS_SEARCHING,
    STATUS_TV_OFFLINE,
)
from .opensubtitles import Candidate, OpenSubtitlesClient, OpenSubtitlesError
from .tv_client import TvClient

_LOGGER = logging.getLogger(__name__)

ACTIVE_STATES = {MediaPlayerState.PLAYING, MediaPlayerState.PAUSED}
SYNC_INTERVAL = timedelta(seconds=10)
MAX_SAVED_MEDIA = 200


class SubtitleManager:
    """Tracks playback and keeps the TV overlay in sync."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        conf = {**entry.data, **entry.options}
        session = async_get_clientsession(hass)
        self.hass = hass
        self.entry = entry
        self.media_entity: str = conf[CONF_MEDIA_PLAYER]
        self.tv = TvClient(session, conf[CONF_HOST], conf[CONF_PORT])
        api_key = (conf.get(CONF_OS_API_KEY) or "").strip()
        self.os: OpenSubtitlesClient | None = (
            OpenSubtitlesClient(
                session,
                api_key,
                (conf.get(CONF_OS_USERNAME) or "").strip(),
                conf.get(CONF_OS_PASSWORD) or "",
            )
            if api_key
            else None
        )
        self.languages = [
            lang.strip().lower()
            for lang in (conf.get(CONF_LANGUAGES) or DEFAULT_LANGUAGES).split(",")
            if lang.strip()
        ]
        self.auto_search: bool = conf.get(CONF_AUTO_SEARCH, True)

        self.candidates: list[Candidate] = []
        self.selected_id: str | None = None
        self.offset_ms = 0
        self.media_key: str | None = None
        self.media_title: str | None = None
        self.last_query = ""
        self.status = STATUS_IDLE
        self.detail: str | None = None
        self.tv_online = False
        self.enabled = True
        self.loaded_name: str | None = None

        self._current: tuple[str, bytes] | None = None
        self._uploads: dict[str, tuple[str, bytes]] = {}
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[Callable[[], None]] = []
        self._media_task: asyncio.Task | None = None
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self._saved: dict[str, dict[str, Any]] = {}

    # ----- lifecycle -----

    async def async_start(self) -> None:
        stored = await self._store.async_load() or {}
        self._saved = stored.get("media", {})
        self._unsubs.append(
            async_track_state_change_event(self.hass, [self.media_entity], self._on_state_event)
        )
        self._unsubs.append(async_track_time_interval(self.hass, self._tick, SYNC_INTERVAL))
        await self._handle_state(self.hass.states.get(self.media_entity))

    async def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._media_task:
            self._media_task.cancel()
        await self._tv(self.tv.set_visible(False))

    # ----- listeners for entities -----

    @callback
    def add_listener(self, cb: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(cb)
        return lambda: self._listeners.remove(cb)

    @callback
    def _notify(self) -> None:
        for cb in list(self._listeners):
            cb()

    def _set_status(self, status: str, detail: str | None = None) -> None:
        self.status = status
        self.detail = detail
        self._notify()

    # ----- candidate labels for the select entity -----

    def candidate_labels(self) -> list[str]:
        return [f"{i + 1}. {c.label}"[:200] for i, c in enumerate(self.candidates)]

    def selected_label(self) -> str | None:
        for label, cand in zip(self.candidate_labels(), self.candidates):
            if cand.id == self.selected_id:
                return label
        return None

    def id_for_label(self, label: str) -> str | None:
        for lbl, cand in zip(self.candidate_labels(), self.candidates):
            if lbl == label:
                return cand.id
        return None

    # ----- playback tracking -----

    @callback
    def _on_state_event(self, event: Event[EventStateChangedData]) -> None:
        self.hass.async_create_task(self._handle_state(event.data["new_state"]))

    async def _handle_state(self, state: State | None) -> None:
        if state is None or state.state not in ACTIVE_STATES:
            await self._tv(self.tv.set_visible(False))
            return

        attrs = state.attributes
        key = attrs.get("media_content_id") or attrs.get("media_title")
        if key and key != self.media_key:
            self.media_key = key
            self.media_title = attrs.get("media_title")
            if self._media_task and not self._media_task.done():
                self._media_task.cancel()
            self._media_task = self.hass.async_create_background_task(
                self._prepare_media(), f"{DOMAIN} prepare media"
            )
        await self._sync(state)

    async def _prepare_media(self) -> None:
        saved = self._saved.get(self.media_key or "", {})
        self.candidates = []
        self._uploads = {}
        self.selected_id = None
        self._current = None
        self.loaded_name = None
        self.offset_ms = int(saved.get("offset_ms", 0))
        await self._tv(self.tv.clear())
        await self._tv(self.tv.set_offset(self.offset_ms))
        self._set_status(STATUS_PLAYING, self.media_title or self.media_key)

        if not self.auto_search:
            return
        await self.async_search(None)
        if not self.candidates:
            return
        ids = [c.id for c in self.candidates]
        target = saved.get("selected_id")
        await self.async_select(target if target in ids else ids[0])

    def _position_ms(self, state: State) -> int:
        attrs = state.attributes
        pos = float(attrs.get("media_position") or 0)
        updated = attrs.get("media_position_updated_at")
        if isinstance(updated, str):
            updated = dt_util.parse_datetime(updated)
        if state.state == MediaPlayerState.PLAYING and isinstance(updated, datetime):
            pos += max(0.0, (dt_util.utcnow() - updated).total_seconds())
        return int(pos * 1000)

    async def _sync(self, state: State | None = None) -> None:
        state = state or self.hass.states.get(self.media_entity)
        if state is None or state.state not in ACTIVE_STATES:
            await self._tv(self.tv.set_visible(False))
            return
        await self._tv(
            self.tv.sync(
                self._position_ms(state), state.state == MediaPlayerState.PLAYING, visible=True
            )
        )

    async def _tick(self, _now: datetime) -> None:
        status = await self._tv(self.tv.status())
        if status is not None and status.get("enabled", True) != self.enabled:
            self.enabled = status.get("enabled", True)
            self._notify()
        if status is not None and self._current and status.get("cues", 0) == 0:
            # The TV app restarted and lost its subtitle.
            await self._push_current()
        else:
            await self._sync()

    # ----- actions used by entities and services -----

    async def async_search(self, query: str | None) -> None:
        if self.os is None:
            self._set_status(STATUS_NO_API_KEY)
            return

        state = self.hass.states.get(self.media_entity)
        attrs = state.attributes if state else {}
        season = episode = None
        if query:
            q = query
        elif series := attrs.get("media_series_title"):
            q = series
            try:
                season = int(attrs["media_season"])
                episode = int(attrs["media_episode"])
            except (KeyError, TypeError, ValueError):
                season = episode = None
        else:
            q = attrs.get("media_title") or ""
        if not q:
            self._set_status(STATUS_NO_TITLE)
            return

        self.last_query = q
        self._set_status(STATUS_SEARCHING, q)
        try:
            results = await self.os.search(q, self.languages, season, episode)
        except (OpenSubtitlesError, aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Subtitle search for %s failed: %s", q, err)
            self._set_status(STATUS_SEARCH_FAILED, str(err))
            return

        uploads = [c for c in self.candidates if c.source == "upload"]
        self.candidates = uploads + results[:MAX_CANDIDATES]
        self._set_status(STATUS_FOUND if results else STATUS_NOT_FOUND, q)

    async def async_select(self, candidate_id: str | None) -> None:
        if candidate_id is None:
            self.selected_id = None
            self._current = None
            self.loaded_name = None
            await self._tv(self.tv.clear())
            self._save()
            self._set_status(STATUS_OFF)
            return

        cand = next((c for c in self.candidates if c.id == candidate_id), None)
        if cand is None:
            raise HomeAssistantError(f"Unknown subtitle {candidate_id}")

        self._set_status(STATUS_DOWNLOADING, cand.label)
        try:
            if cand.source == "upload":
                name, data = self._uploads[cand.id]
            else:
                assert self.os is not None and cand.file_id is not None
                name, data = await self.os.download(cand.file_id)
        except (OpenSubtitlesError, aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Subtitle download failed: %s", err)
            self._set_status(STATUS_DOWNLOAD_FAILED, str(err))
            return

        self._current = (name, data)
        self.selected_id = cand.id
        self._save()
        await self._push_current()

    async def async_upload(self, name: str, data: bytes) -> None:
        cid = f"upload:{len(self._uploads) + 1}"
        self._uploads[cid] = (name, data)
        self.candidates.insert(0, Candidate(id=cid, label=f"⇪ {name}", source="upload"))
        await self.async_select(cid)

    async def async_set_offset(self, offset_ms: int) -> None:
        self.offset_ms = offset_ms
        await self._tv(self.tv.set_offset(offset_ms, notify=True))
        self._save()
        self._notify()

    async def async_set_enabled(self, enabled: bool) -> None:
        if await self._tv(self.tv.set_enabled(enabled)) is not None:
            self.enabled = enabled
            self._notify()

    async def async_set_text_size(self, px: float) -> None:
        await self._tv(self.tv.set_text_size(px))

    # ----- helpers -----

    async def _push_current(self) -> bool:
        if not self._current:
            return False
        name, data = self._current
        try:
            await self.tv.load_subtitle(name, data)
            await self.tv.set_offset(self.offset_ms)
        except aiohttp.ClientResponseError as err:
            self._set_status(STATUS_INVALID_SUBTITLE, err.message)
            return False
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug("TV unreachable: %s", err)
            self.tv_online = False
            self._set_status(STATUS_TV_OFFLINE, name)
            return False
        self.tv_online = True
        self.loaded_name = name
        await self._sync()
        self._set_status(STATUS_LOADED, name)
        return True

    async def _tv(self, coro) -> dict[str, Any] | None:
        try:
            result = await coro
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug("TV request failed: %s", err)
            self._set_online(False)
            return None
        self._set_online(True)
        return result

    def _set_online(self, online: bool) -> None:
        if online != self.tv_online:
            self.tv_online = online
            self._notify()

    def _save(self) -> None:
        if not self.media_key:
            return
        entry = {"offset_ms": self.offset_ms}
        if self.selected_id and not self.selected_id.startswith("upload:"):
            entry["selected_id"] = self.selected_id
        self._saved.pop(self.media_key, None)
        self._saved[self.media_key] = entry
        while len(self._saved) > MAX_SAVED_MEDIA:
            self._saved.pop(next(iter(self._saved)))
        self._store.async_delay_save(lambda: {"media": self._saved}, 5)
