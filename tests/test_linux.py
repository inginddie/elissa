"""Linux helpers that parse what the system answers, and ducking through pactl (faked): they run everywhere."""
import asyncio
import os
import tempfile

os.environ["ELISSA_HOME"] = os.environ.get("ELISSA_HOME") or tempfile.mkdtemp()  # before importing elissa

from elissa import audio_mixer, system
from elissa.system import linux


def test_mpris_metadata():
    meta = {"xesam:title": ("s", "De música ligera"), "xesam:artist": ("as", ["Soda Stereo"]),
            "xesam:album": ("s", "Canción animal"), "mpris:length": ("x", 210000000)}
    assert linux.parse_metadata(meta, "Playing", "Spotify") == {
        "title": "De música ligera", "artist": "Soda Stereo", "album": "Canción animal", "playing": True,
        "player": "Spotify"}
    assert linux.parse_metadata({}, "Stopped", "Vlc") is None
    assert linux._player_label("org.mpris.MediaPlayer2.spotify") == "Spotify"
    assert linux._player_label("org.mpris.MediaPlayer2.firefox.instance_1_42") == "Firefox"


def test_pactl_sink_inputs():
    data = [
        {"index": 42, "corked": False, "volume": {"front-left": {"value": 65536, "value_percent": "100%"},
                                                 "front-right": {"value": 65536, "value_percent": "100%"}},
         "properties": {"application.process.id": "3120", "application.name": "Spotify"}},
        {"index": 43, "corked": True, "volume": {"mono": {"value_percent": "60%"}}, "properties": {}},
        {"index": 44, "volume": {}},
    ]
    assert linux.parse_sink_inputs(data) == [
        {"index": 42, "pid": 3120, "volume": 100, "playing": True},
        {"index": 43, "pid": 0, "volume": 60, "playing": False}]


def test_espeak_voices():
    out = """Pty Language       Age/Gender VoiceName          File                 Other Languages
 5  en-us           --/M      English_(America)  gmw/en-US            (en 3)
 5  es              --/M      Spanish_(Spain)    roa/es
 5  es-419          --/M      Spanish_(Latin_America) roa/es-419      (es-mx 6)
"""
    assert linux.parse_espeak_voices(out) == [
        {"name": "English (America)", "lang": "en-us", "id": "en-us"},
        {"name": "Spanish (Spain)", "lang": "es", "id": "es"},
        {"name": "Spanish (Latin America)", "lang": "es-419", "id": "es-419"}]


def test_desktop_entries(tmp_path, monkeypatch):
    (tmp_path / "firefox.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Firefox\nName[es]=Navegador Firefox\nExec=firefox %u\n", "utf-8")
    (tmp_path / "hidden.desktop").write_text("[Desktop Entry]\nType=Application\nName=X\nExec=x\nNoDisplay=true\n")
    (tmp_path / "link.desktop").write_text("[Desktop Entry]\nType=Link\nName=Web\nURL=https://x\n")
    (tmp_path / "broken.desktop").write_bytes(b"\xff\xfe garbage")
    monkeypatch.setattr(linux, "DESKTOP_DIRS", [tmp_path])
    monkeypatch.setenv("LANG", "es_CO.UTF-8")
    assert linux.list_apps() == [{"name": "Navegador Firefox", "id": str(tmp_path / "firefox.desktop")}]


def test_ducking_with_pactl(monkeypatch):
    streams = {42: {"index": 42, "pid": 3120, "volume": 100, "playing": True},
               43: {"index": 43, "pid": 999, "volume": 80, "playing": True},  # Elissa's own WebView
               44: {"index": 44, "pid": 555, "volume": 70, "playing": False}}  # paused: left alone
    monkeypatch.setattr(system, "IS_WINDOWS", False)
    monkeypatch.setattr(system, "IS_MAC", False)
    monkeypatch.setattr(system, "IS_LINUX", True)
    monkeypatch.setattr(system, "CAPS", system.CAPS | {"mixer"})
    monkeypatch.setattr(linux, "sink_inputs", lambda: [dict(s) for s in streams.values()])
    monkeypatch.setattr(linux, "set_sink_input_volume", lambda i, v: streams[i].update(volume=v))
    mixer = audio_mixer.Mixer(own_pids=lambda: {999})
    asyncio.run(mixer.duck(0.2))
    assert [streams[i]["volume"] for i in (42, 43, 44)] == [20, 80, 70]
    asyncio.run(mixer.restore())
    assert streams[42]["volume"] == 100
    asyncio.run(mixer.duck(0.2))
    streams[42]["volume"] = 55  # the user moved it meanwhile
    asyncio.run(mixer.restore())
    assert streams[42]["volume"] == 55
