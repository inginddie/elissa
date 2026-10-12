"""Volume: the system volume, and lowering other apps (ducking) while Elissa listens and answers.

Ducking lowers every app that is playing (Spotify, a browser, a game…) to a fraction of its own volume, never Elissa
herself, and gives each one back its volume afterwards. Safety rules: an app whose volume the user changed meanwhile
is left alone, and the volume always comes back when the conversation ends, the window goes away, the engine exits,
or after MAX_DUCK_S at the latest.

Windows' audio API is COM, so every call runs on one worker thread that initialized COM.
"""
import asyncio
import atexit
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger(__name__)

MAX_DUCK_S = 180
ACTIVE = 1  # AudioSessionStateActive
TOLERANCE = 0.02


def _init_com() -> None:
    import comtypes
    comtypes.CoInitialize()


class Mixer:
    def __init__(self, own_pids=lambda: {os.getpid()}):
        self.own_pids = own_pids  # Elissa's own processes (engine, shell, its WebView2) are never ducked
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mixer", initializer=_init_com)
        self._ducked: dict[int, tuple[float, float]] = {}  # pid -> (original volume, ducked volume)
        self._since = 0.0
        atexit.register(self.restore_now)

    async def _run(self, fn, *args):
        return await asyncio.get_running_loop().run_in_executor(self._pool, fn, *args)

    # ----- system volume -----

    @staticmethod
    def _endpoint():
        from pycaw.pycaw import AudioUtilities
        return AudioUtilities.GetSpeakers().EndpointVolume

    def _get_volume(self) -> dict:
        ev = self._endpoint()
        return {"percent": round(ev.GetMasterVolumeLevelScalar() * 100), "muted": bool(ev.GetMute())}

    def _set_volume(self, percent: int | None, delta: int | None, mute: bool | None) -> dict:
        ev = self._endpoint()
        current = ev.GetMasterVolumeLevelScalar() * 100
        if percent is not None or delta is not None:
            target = percent if percent is not None else current + delta
            ev.SetMasterVolumeLevelScalar(max(0.0, min(100.0, float(target))) / 100, None)
            if mute is None:
                ev.SetMute(0, None)  # asking for a volume means wanting to hear it
        if mute is not None:
            ev.SetMute(1 if mute else 0, None)
        return self._get_volume()

    async def volume(self) -> dict:
        return await self._run(self._get_volume)

    async def set_volume(self, percent: int | None = None, delta: int | None = None, mute: bool | None = None) -> dict:
        return await self._run(self._set_volume, percent, delta, mute)

    # ----- ducking -----

    def _sessions(self):
        from pycaw.pycaw import AudioUtilities
        return AudioUtilities.GetAllSessions()

    def _duck(self, level: float) -> int:
        own = self.own_pids()
        count = 0
        for s in self._sessions():
            pid = s.ProcessId
            if not pid or pid in own or pid in self._ducked or s.State != ACTIVE:
                continue
            vol = s.SimpleAudioVolume
            original = vol.GetMasterVolume()
            target = round(original * level, 3)
            if original <= TOLERANCE:
                continue
            vol.SetMasterVolume(target, None)
            self._ducked[pid] = (original, target)
            count += 1
        if count:
            self._since = time.monotonic()
        return count

    def _restore(self) -> int:
        count = 0
        for s in self._sessions():
            entry = self._ducked.get(s.ProcessId)
            if not entry:
                continue
            original, target = entry
            vol = s.SimpleAudioVolume
            if abs(vol.GetMasterVolume() - target) <= TOLERANCE:  # the user didn't change it meanwhile
                vol.SetMasterVolume(original, None)
                count += 1
        self._ducked.clear()
        return count

    async def duck(self, level: float) -> None:
        if not 0 <= level < 1:
            return
        try:
            n = await self._run(self._duck, level)
            if n:
                log.info("ducked %d app(s) to %d%%", n, round(level * 100))
        except Exception:
            log.exception("could not lower other apps")

    async def restore(self) -> None:
        if not self._ducked:
            return
        try:
            n = await self._run(self._restore)
            log.info("restored the volume of %d app(s)", n)
        except Exception:
            log.exception("could not restore other apps")

    async def watchdog(self) -> None:
        """Never leave the music low: restore after MAX_DUCK_S whatever happens."""
        if self._ducked and time.monotonic() - self._since > MAX_DUCK_S:
            await self.restore()

    def restore_now(self) -> None:
        """Synchronous, for exit paths."""
        if self._ducked:
            try:
                self._pool.submit(self._restore).result(timeout=3)
            except Exception:
                log.exception("could not restore other apps on exit")
