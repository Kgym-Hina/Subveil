"""Base entity for Subveil."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .manager import SubtitleManager


class SubveilEntity(Entity):
    """Entity that refreshes whenever the manager changes."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: SubtitleManager, key: str) -> None:
        self.manager = manager
        self._attr_translation_key = key
        self._attr_unique_id = f"{manager.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, manager.entry.entry_id)},
            name="Subveil",
            manufacturer="Subveil",
            model="Android TV overlay",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.manager.add_listener(self.async_write_ha_state))
