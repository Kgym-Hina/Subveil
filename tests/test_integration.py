"""End-to-end tests with a mocked TV app and OpenSubtitles API."""

from datetime import timedelta

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.subveil.const import DOMAIN

TV = "http://192.0.2.10:8765"
OS = "https://api.opensubtitles.com/api/v1"
PLAYER = "media_player.apple_tv"
SRT = b"1\n00:00:01,000 --> 00:00:02,000\nhello\n"
CONFIG = {
    "host": "192.0.2.10",
    "port": 8765,
    "media_player": PLAYER,
    "opensubtitles_api_key": "k",
    "languages": "zh-cn,en",
    "auto_search": True,
}

SEARCH = {
    "data": [
        {"attributes": {"language": "zh-CN", "release": "Interstellar.Animals", "download_count": 9000,
                        "feature_details": {"title": "Interstellar Animals"},
                        "files": [{"file_id": 3, "file_name": "other.srt"}]}},
        {"attributes": {"language": "en", "release": "Interstellar.EN", "download_count": 900,
                        "feature_details": {"title": "Interstellar"},
                        "files": [{"file_id": 2, "file_name": "en.srt"}]}},
        {"attributes": {"language": "zh-CN", "release": "Interstellar.CHS", "download_count": 50,
                        "feature_details": {"title": "Interstellar"},
                        "files": [{"file_id": 1, "file_name": "zh.srt"}]}},
    ]
}


def mock_tv(aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(f"{TV}/status", json={"ok": True, "cues": 1})
    for path in ("subtitle", "clear", "sync", "offset", "visible", "style"):
        aioclient_mock.post(f"{TV}/{path}", json={"ok": True, "cues": 1})


def mock_os(aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(f"{OS}/subtitles", json=SEARCH)
    aioclient_mock.post(f"{OS}/download", json={"link": "https://dl.example/x.srt", "file_name": "zh.srt"})
    aioclient_mock.get("https://dl.example/x.srt", content=SRT)


def calls(aioclient_mock, path):
    return [c for c in aioclient_mock.mock_calls if str(c[1]).split("?")[0].endswith(path)]


def entity_id(hass, platform, entry, key):
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")


async def test_config_flow(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    mock_tv(aioclient_mock)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CONFIG)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Subveil (192.0.2.10)"


async def test_config_flow_cannot_connect(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(f"{TV}/status", exc=TimeoutError())
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CONFIG)
    assert result["errors"] == {"base": "cannot_connect"}


async def setup(hass, aioclient_mock):
    mock_tv(aioclient_mock)
    mock_os(aioclient_mock)
    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_auto_match_and_controls(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, tmp_path) -> None:
    entry = await setup(hass, aioclient_mock)
    select = entity_id(hass, "select", entry, "subtitle")
    number = entity_id(hass, "number", entry, "offset")
    status = entity_id(hass, "sensor", entry, "status")

    updated = dt_util.utcnow() - timedelta(seconds=10)
    hass.states.async_set(PLAYER, "playing", {
        "media_content_id": "PMTFY26FTR022", "media_title": "Interstellar",
        "media_position": 132, "media_position_updated_at": updated,
    })
    await hass.async_block_till_done()

    # Exact title matches rank first, then preferred language, then downloads.
    assert hass.states.get(select).state.startswith("1. [zh-cn] Interstellar.CHS")
    assert hass.states.get(status).state == "loaded"
    assert len(calls(aioclient_mock, "/subtitle")) == 1
    sync = calls(aioclient_mock, "/sync")[-1][2]
    assert sync["playing"] is True and 141000 <= sync["position_ms"] <= 144000

    await hass.services.async_call("number", "set_value", {"entity_id": number, "value": 1.5}, blocking=True)
    assert calls(aioclient_mock, "/offset")[-1][2] == {"offset_ms": 1500}

    earlier = er.async_get(hass).async_get_entity_id("button", DOMAIN, f"{entry.entry_id}_offset_earlier_1000")
    await hass.services.async_call("button", "press", {"entity_id": earlier}, blocking=True)
    assert calls(aioclient_mock, "/offset")[-1][2] == {"offset_ms": 500}

    options = hass.states.get(select).attributes["options"]
    await hass.services.async_call("select", "select_option", {"entity_id": select, "option": options[2]}, blocking=True)
    assert len(calls(aioclient_mock, "/subtitle")) == 2

    f = tmp_path / "mine.srt"
    f.write_bytes(SRT)
    hass.config.allowlist_external_dirs.add(str(tmp_path))
    await hass.services.async_call(DOMAIN, "upload_subtitle", {"path": str(f)}, blocking=True)
    assert hass.states.get(select).state == "1. ⇪ mine.srt"
    assert calls(aioclient_mock, "/subtitle")[-1][2] == SRT

    hass.states.async_set(PLAYER, "idle", {})
    await hass.async_block_till_done()
    assert calls(aioclient_mock, "/visible")[-1][2] == {"visible": False}


async def test_unload(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    entry = await setup(hass, aioclient_mock)
    assert await hass.config_entries.async_unload(entry.entry_id)
