"""Subtitle offset."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import SubveilEntity


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([SubtitleOffset(entry.runtime_data, "offset")])


class SubtitleOffset(SubveilEntity, NumberEntity):
    """Positive values show subtitles later."""

    _attr_native_min_value = -600
    _attr_native_max_value = 600
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.BOX

    @property
    def native_value(self) -> float:
        return self.manager.offset_ms / 1000

    async def async_set_native_value(self, value: float) -> None:
        await self.manager.async_set_offset(round(value * 1000))
