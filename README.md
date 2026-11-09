<p align="center"><img src="docs/icon.png" width="128" alt="Subveil icon"></p>

<h1 align="center">Subveil</h1>

<p align="center">
External subtitles on top of any HDMI input, driven by Home Assistant.<br>
<a href="README.zh-CN.md">中文说明</a>
</p>

Subveil shows synchronized subtitles over what your Android TV displays, including HDMI inputs such as an Apple TV. A small Android app draws a transparent overlay at the bottom of the screen. A Home Assistant integration follows your media player, finds matching subtitles on OpenSubtitles, and keeps them in time with playback.

```
Apple TV ──(Home Assistant media player)──> Home Assistant ──HTTP :8765──> Subveil app (overlay on the TV)
                                                 │
                                                 └──> OpenSubtitles.com
```

## Features

- Subtitles over HDMI inputs and any app on Android TV / Google TV.
- Automatic search when a new title starts playing (movies by title, shows by series + season + episode), ranked by exact title match, your language order and popularity.
- Pick another subtitle, nudge the timing and change the text size from Home Assistant. Offset and choice are remembered per title.
- Upload your own SRT, WebVTT or ASS/SSA files from Home Assistant or from a web page served by the TV app. UTF-8, UTF-16 and GBK files are supported.
- Starts at boot and recovers automatically when the TV app restarts.

## Requirements

- An Android TV with Android 8.0 or newer and ADB debugging enabled (used once, to grant the overlay permission).
- Home Assistant 2026.3 or newer with a media player entity for your source, e.g. the [Apple TV integration](https://www.home-assistant.io/integrations/apple_tv/).
- An [OpenSubtitles.com API key](https://www.opensubtitles.com/en/consumers) (free).

Whether the overlay stays visible over HDMI depends on the TV. It has been tested on a Xiaomi TV (HyperOS, Android 14) with an Apple TV input.

## 1. Install the TV app

1. Download `subveil-x.y.z.apk` from the [latest release](https://github.com/Kgym-Hina/Subveil/releases/latest).
2. Install it and grant the overlay permission over ADB:

   ```sh
   adb connect <tv-ip>:5555
   adb install subveil-0.1.0.apk
   adb shell appops set io.github.kgymhina.subveil SYSTEM_ALERT_WINDOW allow
   adb shell am start-foreground-service -n io.github.kgymhina.subveil/.OverlayService
   ```

3. Open `http://<tv-ip>:8765` in a browser to check that it is running.

Give the TV a fixed IP address in your router so Home Assistant can always reach it.

> **Xiaomi TVs:** the system kills an app that owns an overlay when you leave its screen. Subveil works around this by removing the overlay while its own screen is open and restoring it 3 seconds after you leave. Starting the service directly (the last `adb` command above) avoids the issue entirely. If the app does not start after a reboot, allow auto-start for Subveil in the TV settings.

## 2. Install the Home Assistant integration

### HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Kgym-Hina&repository=Subveil&category=integration)

Or in HACS, open the menu, choose **Custom repositories**, add `https://github.com/Kgym-Hina/Subveil` as an **Integration**, then download **Subveil** and restart Home Assistant.

### Manual

Copy `custom_components/subveil` into your Home Assistant `config/custom_components/` folder and restart Home Assistant.

### Set up

Go to **Settings → Devices & services → Add integration → Subveil** and enter:

| Field | Description |
|---|---|
| TV IP address / port | The TV running Subveil, port `8765` |
| Media player | The player subtitles should follow, e.g. `media_player.living_room_apple_tv` |
| OpenSubtitles API key | From opensubtitles.com → API consumers |
| Username / password | Optional. Needed if your API key does not allow anonymous downloads |
| Subtitle languages | Comma-separated, in order of preference, e.g. `zh-cn,en` |
| Search automatically | Search and load the best match when a new title starts |

All of these except the TV address can be changed later under **Configure**.

## Entities

| Entity | Purpose |
|---|---|
| `select` Subtitle | Switch between search results and uploaded files, or turn subtitles off |
| `number` Subtitle offset | Seconds; positive values show subtitles later. Saved per title |
| `button` Subtitles 1 s / 0.1 s earlier / later | Quick timing nudges; the TV briefly shows the new offset |
| `button` Search again | Search again using the current title |
| `text` Search query | Type a title to search manually |
| `sensor` Status | Current state; attributes include TV connectivity, title and subtitle file |

## Actions

- `subveil.upload_subtitle`: load a file by `path` (must be in an allowed directory such as `/media` or `/config/www`) or pass the subtitle text as `content`.
- `subveil.search`: search OpenSubtitles; without `query` the current title is used.
- `subveil.set_text_size`: set the text size in pixels (1080p screen).

## How syncing works

Home Assistant reports `media_position` and `media_position_updated_at` for the player. Subveil sends the position to the TV on every play, pause or seek and re-syncs every 10 seconds; between updates the TV app advances the clock itself. When playback stops, the overlay is hidden.

Your source player only reports the title, not the release or year, so a match can occasionally be the wrong edition. Pick another entry from the list or adjust the offset.

## TV app HTTP API

The app listens on port `8765` without authentication; keep it on your local network.

| Method | Path | Body |
|---|---|---|
| GET | `/` | Upload page |
| GET | `/status` | Current state as JSON |
| POST | `/subtitle?name=file.srt` | Raw subtitle file (SRT / VTT / ASS) |
| POST | `/sync` | `{"position_ms": 132000, "playing": true, "visible": true}` |
| POST | `/offset[?notify=1]` | `{"offset_ms": 1500}` |
| POST | `/visible` | `{"visible": false}` |
| POST | `/style` | `{"text_size_px": 40}` |
| POST | `/clear` | |

## Building from source

The Android app has no Gradle build and no third-party dependencies.

```sh
# Needs JDK 17 and Android SDK build-tools 35 + platform 34
cd android
./build.sh            # signs with a generated debug key
./install.sh          # installs on the TV connected via adb
```

Set `SUBVEIL_KEYSTORE`, `SUBVEIL_KEYSTORE_PASS` and `SUBVEIL_KEY_ALIAS` to sign with your own key.

Integration tests:

```sh
pip install -r requirements_test.txt
pytest
```

## License

[MIT](LICENSE). Subtitles are provided by [OpenSubtitles.com](https://www.opensubtitles.com); Subveil is not affiliated with OpenSubtitles.
