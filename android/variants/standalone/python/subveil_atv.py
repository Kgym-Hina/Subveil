"""Bridge between the Java service and pyatv.

All pyatv work runs on one asyncio loop in a background thread. Java calls the
module-level functions from its own threads; they block until the coroutine is done
and return JSON strings.
"""

import asyncio
import json
import logging
import os
import threading
import time

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

import pyatv  # noqa: E402
from pyatv.const import OperatingSystem, PairingRequirement, Protocol  # noqa: E402
from pyatv.interface import DeviceListener, PushListener  # noqa: E402

_LOGGER = logging.getLogger("subveil_atv")
_RECONNECT_DELAY = 10

_loop = asyncio.new_event_loop()
threading.Thread(target=_loop.run_forever, name="pyatv", daemon=True).start()


def _run(coro, timeout=60):
    return asyncio.run_coroutine_threadsafe(coro, _loop).result(timeout)


class _State:
    def __init__(self):
        self.wanted = None  # (identifier, address, credentials)
        self.atv = None
        self.task = None
        self.status = "idle"
        self.error = ""
        self.device = ""
        self.playing = None
        self.updated = 0.0
        self.lost = None
        self.pairing = None


_s = _State()


def _playing_dict(p, app):
    return {
        "title": p.title or "",
        "series": p.series_name or "",
        "season": p.season_number,
        "episode": p.episode_number,
        "position_s": p.position,
        "total_s": p.total_time,
        "state": p.device_state.name.lower() if p.device_state else "idle",
        "media_type": p.media_type.name.lower() if p.media_type else "unknown",
        "app": app,
    }


class _Listener(PushListener, DeviceListener):
    def playstatus_update(self, updater, playstatus):
        app = ""
        try:
            if _s.atv is not None:
                app_info = _s.atv.metadata.app
                app = (app_info.name or app_info.identifier or "") if app_info else ""
        except Exception:  # noqa: BLE001 - app info is optional
            pass
        _s.playing = _playing_dict(playstatus, app)
        _s.updated = time.monotonic()

    def playstatus_error(self, updater, exception):
        _LOGGER.warning("push error: %s", exception)

    def connection_lost(self, exception):
        _LOGGER.warning("connection lost: %s", exception)
        if _s.lost:
            _s.lost.set()

    def connection_closed(self):
        if _s.lost:
            _s.lost.set()


_listener = _Listener()


async def _find(identifier, address, timeout=5):
    hosts = [address] if address else None
    confs = await pyatv.scan(_loop, identifier=identifier, hosts=hosts, timeout=timeout)
    if not confs and hosts:
        confs = await pyatv.scan(_loop, identifier=identifier, timeout=timeout)
    if not confs:
        raise RuntimeError("Apple TV not found on the network")
    return confs[0]


async def _scan(timeout):
    out = []
    for conf in await pyatv.scan(_loop, timeout=timeout):
        airplay = conf.get_service(Protocol.AirPlay)
        # Macs and AirPlay receivers built into TVs also answer the scan. TV receivers
        # pose as tvOS devices, but only real Apple TVs offer Companion.
        if (
            airplay is None
            or conf.get_service(Protocol.Companion) is None
            or conf.device_info.operating_system != OperatingSystem.TvOS
        ):
            continue
        out.append({
            "id": conf.identifier,
            "name": conf.name,
            "address": str(conf.address),
            "model": conf.device_info.model_str,
            "version": conf.device_info.version or "",
            "needs_pairing": airplay.pairing == PairingRequirement.Mandatory,
        })
    return out


def scan(timeout=5):
    return json.dumps(_run(_scan(timeout)))


async def _pair_begin(identifier, address):
    if _s.pairing is not None:
        await _s.pairing.close()
        _s.pairing = None
    conf = await _find(identifier, address)
    pairing = await pyatv.pair(conf, Protocol.AirPlay, _loop, name="Subveil")
    await pairing.begin()
    _s.pairing = pairing
    return {"device_provides_pin": pairing.device_provides_pin}


def pair_begin(identifier, address=""):
    return json.dumps(_run(_pair_begin(identifier, address or None)))


async def _pair_finish(pin):
    pairing = _s.pairing
    if pairing is None:
        raise RuntimeError("pairing was not started")
    try:
        pairing.pin(int(pin))
        await pairing.finish()
        if not pairing.has_paired:
            raise RuntimeError("pairing failed, check the PIN")
        return {"credentials": pairing.service.credentials}
    finally:
        await pairing.close()
        _s.pairing = None


def pair_finish(pin):
    return json.dumps(_run(_pair_finish(pin)))


async def _maintain():
    while _s.wanted is not None:
        identifier, address, credentials = _s.wanted
        _s.status = "connecting"
        try:
            conf = await _find(identifier, address)
            conf.set_credentials(Protocol.AirPlay, credentials)
            _s.device = conf.name
            atv = await pyatv.connect(conf, _loop)
            _s.atv = atv
            _s.lost = asyncio.Event()
            atv.listener = _listener
            atv.push_updater.listener = _listener
            atv.push_updater.start()
            _s.status = "connected"
            _s.error = ""
            await _s.lost.wait()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 - reported to the web page
            _LOGGER.warning("connect failed: %r", e)
            _s.error = str(e) or type(e).__name__
            _s.status = "error"
        finally:
            if _s.atv is not None:
                _s.atv.close()
                _s.atv = None
            _s.playing = None
        await asyncio.sleep(_RECONNECT_DELAY)


async def _connect(identifier, address, credentials):
    await _disconnect()
    _s.wanted = (identifier, address or None, credentials)
    _s.task = _loop.create_task(_maintain())


def connect(identifier, address, credentials):
    _run(_connect(identifier, address, credentials))


async def _disconnect():
    _s.wanted = None
    if _s.task is not None:
        _s.task.cancel()
        try:
            await _s.task
        except BaseException:  # noqa: BLE001
            pass
        _s.task = None
    _s.status = "idle"
    _s.error = ""
    _s.playing = None


def disconnect():
    _run(_disconnect())


def status():
    out = {"status": _s.status, "error": _s.error, "device": _s.device}
    p = _s.playing
    if p is not None:
        p = dict(p)
        position = p.get("position_s")
        if position is not None:
            elapsed = time.monotonic() - _s.updated if p["state"] == "playing" else 0
            p["position_ms"] = int((position + elapsed) * 1000)
        out["playing"] = p
    return json.dumps(out)
