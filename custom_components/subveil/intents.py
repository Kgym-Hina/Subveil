"""Voice (Assist) intents for Subveil."""

from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_SHIFT_S = 0.5

# intent name -> (English reply, Chinese reply)
_REPLIES = {
    "SubveilSubtitlesOn": ("Subtitles on", "字幕已开启"),
    "SubveilSubtitlesOff": ("Subtitles off", "字幕已关闭"),
    "SubveilMatchSubtitles": ("Looking for subtitles", "正在匹配字幕"),
    "SubveilOffsetLater": ("Subtitles shifted later", "字幕已延后"),
    "SubveilOffsetEarlier": ("Subtitles shifted earlier", "字幕已提前"),
    "SubveilOffsetReset": ("Subtitle timing reset", "字幕时间已归零"),
}


class SubveilIntentHandler(intent.IntentHandler):
    """Runs one Subveil action on the loaded config entry."""

    def __init__(self, intent_type: str) -> None:
        self.intent_type = intent_type

    @property
    def slot_schema(self) -> dict:
        return {vol.Optional("seconds"): vol.Coerce(float)}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        hass = intent_obj.hass
        entries = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.state is ConfigEntryState.LOADED
        ]
        if not entries:
            raise intent.IntentHandleError("Subveil is not set up")
        manager = entries[0].runtime_data
        seconds = self._slots(intent_obj).get("seconds", DEFAULT_SHIFT_S)

        match self.intent_type:
            case "SubveilSubtitlesOn":
                await manager.async_set_enabled(True)
            case "SubveilSubtitlesOff":
                await manager.async_set_enabled(False)
            case "SubveilMatchSubtitles":
                await manager.async_search(None)
                if manager.candidates:
                    await manager.async_select(manager.candidates[0].id)
            case "SubveilOffsetLater":
                await manager.async_set_offset(manager.offset_ms + round(seconds * 1000))
            case "SubveilOffsetEarlier":
                await manager.async_set_offset(manager.offset_ms - round(seconds * 1000))
            case "SubveilOffsetReset":
                await manager.async_set_offset(0)

        english, chinese = _REPLIES[self.intent_type]
        response = intent_obj.create_response()
        response.async_set_speech(chinese if intent_obj.language.startswith("zh") else english)
        return response

    @staticmethod
    def _slots(intent_obj: intent.Intent) -> dict:
        return {k: v["value"] for k, v in intent_obj.slots.items()}


def async_setup_intents(hass: HomeAssistant) -> None:
    for name in _REPLIES:
        intent.async_register(hass, SubveilIntentHandler(name))


def _install_sentences(config_dir: Path, source: Path) -> bool:
    """Copies the bundled sentence files into <config>/custom_sentences if missing."""
    copied = False
    for src in source.glob("*/subveil.yaml"):
        dest = config_dir / "custom_sentences" / src.parent.name / "subveil.yaml"
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        copied = True
    return copied


async def async_install_sentences(hass: HomeAssistant) -> None:
    source = Path(__file__).parent / "custom_sentences"
    try:
        copied = await hass.async_add_executor_job(
            _install_sentences, Path(hass.config.config_dir), source
        )
    except OSError as err:
        _LOGGER.warning("Could not install voice sentences: %s", err)
        return
    if copied and hass.services.has_service("conversation", "reload"):
        await hass.services.async_call("conversation", "reload", blocking=False)
