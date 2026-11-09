"""Manual subtitle search query."""

from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import SubveilEntity


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([SearchQuery(entry.runtime_data, "search_query")])


class SearchQuery(SubveilEntity, TextEntity):
    _attr_native_max = 255

    @property
    def native_value(self) -> str:
        return self.manager.last_query

    async def async_set_value(self, value: str) -> None:
        await self.manager.async_search(value.strip() or None)
