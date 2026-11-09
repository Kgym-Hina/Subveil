"""Status sensor."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import STATUSES
from .entity import SubveilEntity


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([StatusSensor(entry.runtime_data, "status")])


class StatusSensor(SubveilEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUSES

    @property
    def native_value(self) -> str:
        return self.manager.status

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        m = self.manager
        return {
            "detail": m.detail,
            "tv_online": m.tv_online,
            "media_title": m.media_title,
            "media_key": m.media_key,
            "subtitle": m.loaded_name,
            "offset_ms": m.offset_ms,
            "candidates": len(m.candidates),
            "last_query": m.last_query,
        }
