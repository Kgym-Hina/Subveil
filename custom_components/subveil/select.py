"""Subtitle picker."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import SubveilEntity

OFF_OPTION = "Off"


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([SubtitleSelect(entry.runtime_data, "subtitle")])


class SubtitleSelect(SubveilEntity, SelectEntity):
    @property
    def options(self) -> list[str]:
        return [OFF_OPTION, *self.manager.candidate_labels()]

    @property
    def current_option(self) -> str:
        return self.manager.selected_label() or OFF_OPTION

    async def async_select_option(self, option: str) -> None:
        await self.manager.async_select(
            None if option == OFF_OPTION else self.manager.id_for_label(option)
        )
