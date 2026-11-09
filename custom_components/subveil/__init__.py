"""Subveil: external subtitles over HDMI input via an Android TV overlay."""

from __future__ import annotations

from pathlib import Path

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .manager import SubtitleManager

PLATFORMS = [Platform.BUTTON, Platform.NUMBER, Platform.SELECT, Platform.SENSOR, Platform.TEXT]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

ATTR_ENTRY = "config_entry_id"

UPLOAD_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY): cv.string,
        vol.Optional("path"): cv.string,
        vol.Optional("content"): cv.string,
        vol.Optional("filename"): cv.string,
    }
)
SEARCH_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_ENTRY): cv.string, vol.Optional("query"): cv.string}
)
TEXT_SIZE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY): cv.string,
        vol.Required("size"): vol.All(vol.Coerce(float), vol.Range(min=12, max=200)),
    }
)

type SubveilConfigEntry = ConfigEntry[SubtitleManager]


def _manager(hass: HomeAssistant, call: ServiceCall) -> SubtitleManager:
    entries = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.state is ConfigEntryState.LOADED
    ]
    if entry_id := call.data.get(ATTR_ENTRY):
        entries = [e for e in entries if e.entry_id == entry_id]
    if not entries:
        raise ServiceValidationError("No loaded Subveil entry found")
    if len(entries) > 1:
        raise ServiceValidationError("Several entries are loaded; pass config_entry_id")
    return entries[0].runtime_data


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async def upload(call: ServiceCall) -> None:
        manager = _manager(hass, call)
        if path := call.data.get("path"):
            if not hass.config.is_allowed_path(path):
                raise ServiceValidationError(
                    f"{path} is not in allowlist_external_dirs (e.g. /media or /config/www)"
                )
            try:
                data = await hass.async_add_executor_job(Path(path).read_bytes)
            except OSError as err:
                raise ServiceValidationError(f"Cannot read {path}: {err}") from err
            name = call.data.get("filename") or Path(path).name
        elif content := call.data.get("content"):
            data = content.encode("utf-8")
            name = call.data.get("filename") or "upload.srt"
        else:
            raise ServiceValidationError("Provide either path or content")
        await manager.async_upload(name, data)

    async def search(call: ServiceCall) -> None:
        await _manager(hass, call).async_search(call.data.get("query"))

    async def text_size(call: ServiceCall) -> None:
        await _manager(hass, call).async_set_text_size(call.data["size"])

    hass.services.async_register(DOMAIN, "upload_subtitle", upload, schema=UPLOAD_SCHEMA)
    hass.services.async_register(DOMAIN, "search", search, schema=SEARCH_SCHEMA)
    hass.services.async_register(DOMAIN, "set_text_size", text_size, schema=TEXT_SIZE_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SubveilConfigEntry) -> bool:
    manager = SubtitleManager(hass, entry)
    entry.runtime_data = manager
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await manager.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: SubveilConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SubveilConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded
