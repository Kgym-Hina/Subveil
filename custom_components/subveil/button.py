"""Buttons: re-run the search and nudge the subtitle offset."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import SubveilEntity
from .manager import SubtitleManager

NUDGES_MS = (-1000, -100, 100, 1000)


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    manager = entry.runtime_data
    async_add_entities(
        [
            ResearchButton(manager, "research"),
            *(OffsetNudgeButton(manager, delta) for delta in NUDGES_MS),
        ]
    )


class ResearchButton(SubveilEntity, ButtonEntity):
    async def async_press(self) -> None:
        await self.manager.async_search(None)


class OffsetNudgeButton(SubveilEntity, ButtonEntity):
    """Positive deltas show subtitles later."""

    def __init__(self, manager: SubtitleManager, delta_ms: int) -> None:
        direction = "later" if delta_ms > 0 else "earlier"
        super().__init__(manager, f"offset_{direction}")
        self._attr_unique_id = f"{manager.entry.entry_id}_offset_{direction}_{abs(delta_ms)}"
        self._attr_translation_placeholders = {"seconds": f"{abs(delta_ms) / 1000:g}"}
        self._delta_ms = delta_ms

    async def async_press(self) -> None:
        await self.manager.async_set_offset(self.manager.offset_ms + self._delta_ms)
