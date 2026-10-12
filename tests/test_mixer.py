"""Ducking and volume with fake Windows audio sessions: who gets lowered, and that the volume always comes back."""
import asyncio
import os
import tempfile

os.environ["ELISSA_HOME"] = os.environ.get("ELISSA_HOME") or tempfile.mkdtemp()  # before importing elissa

from elissa import audio_mixer
from elissa.audio_mixer import Mixer


class Vol:
    def __init__(self, v):
        self.v = v

    def GetMasterVolume(self):
        return self.v

    def SetMasterVolume(self, v, _ctx):
        self.v = v


class Session:
    def __init__(self, pid, volume=1.0, active=True):
        self.ProcessId, self.SimpleAudioVolume, self.State = pid, Vol(volume), 1 if active else 0


def make(sessions, own=(1,)):
    m = Mixer(own_pids=lambda: set(own))
    m._sessions = lambda: sessions
    return m


def test_ducks_only_other_playing_apps_and_restores():
    spotify, chrome, elissa, idle = Session(10, 0.8), Session(11, 1.0), Session(1), Session(12, 1.0, active=False)
    m = make([spotify, chrome, elissa, idle])
    asyncio.run(m.duck(0.2))
    assert spotify.SimpleAudioVolume.v == 0.16 and chrome.SimpleAudioVolume.v == 0.2
    assert elissa.SimpleAudioVolume.v == 1.0 and idle.SimpleAudioVolume.v == 1.0
    asyncio.run(m.duck(0.2))  # listening again in the same conversation: no double ducking
    assert spotify.SimpleAudioVolume.v == 0.16
    asyncio.run(m.restore())
    assert spotify.SimpleAudioVolume.v == 0.8 and chrome.SimpleAudioVolume.v == 1.0


def test_a_volume_the_user_changed_is_left_alone():
    s = Session(10)
    m = make([s])
    asyncio.run(m.duck(0.2))
    s.SimpleAudioVolume.v = 0.6
    asyncio.run(m.restore())
    assert s.SimpleAudioVolume.v == 0.6


def test_off_and_watchdog(monkeypatch):
    s = Session(10)
    m = make([s])
    asyncio.run(m.duck(1.0))  # 1 = leave other apps alone
    assert s.SimpleAudioVolume.v == 1.0
    asyncio.run(m.duck(0.2))
    clock = [audio_mixer.time.monotonic() + audio_mixer.MAX_DUCK_S + 1]
    monkeypatch.setattr(audio_mixer.time, "monotonic", lambda: clock[0])
    asyncio.run(m.watchdog())
    assert s.SimpleAudioVolume.v == 1.0


def test_restore_now_for_exit_paths():
    s = Session(10)
    m = make([s])
    asyncio.run(m.duck(0.2))
    m.restore_now()
    assert s.SimpleAudioVolume.v == 1.0


def test_session_tools():
    from elissa.tools import ToolRegistry
    from elissa.tools.session import register
    sent = []

    class FakeMixer:
        async def volume(self):
            return {"percent": 40, "muted": False}

        async def set_volume(self, percent=None, delta=None, mute=None):
            return {"percent": percent if percent is not None else 40 + (delta or 0), "muted": bool(mute)}

    reg = ToolRegistry()
    register(reg, FakeMixer(), sent.append)
    tools = reg._tools
    assert asyncio.run(tools["volumen"].fn(cambio=-20)) == "Volumen del sistema: 20 %."
    assert asyncio.run(tools["volumen"].fn()) == "Volumen del sistema: 40 %."
    asyncio.run(tools["terminar_conversacion"].fn(ocultar=True))
    assert sent == [{"type": "end_conversation", "hide": True}]
