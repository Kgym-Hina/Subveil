"""Global subtitle on/off switch."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import SubveilEntity


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([SubtitlesSwitch(entry.runtime_data, "subtitles")])


class SubtitlesSwitch(SubveilEntity, SwitchEntity):
    """Shows or hides all subtitles on the TV. The TV keeps the setting."""

    @property
    def is_on(self) -> bool:
        return self.manager.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.manager.async_set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.manager.async_set_enabled(False)
