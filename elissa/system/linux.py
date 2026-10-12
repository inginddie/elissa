"""Linux: XDG .desktop apps, MPRIS players over D-Bus, PulseAudio/PipeWire volume (pactl), espeak-ng, logind.

Each capability is on only when what it needs is there (pactl, espeak-ng, a D-Bus session, curl…), so a minimal
system just gets fewer tools instead of failing ones.
"""
import configparser
import ctypes
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

DESKTOP_DIRS = [Path.home() / ".local/share/applications", Path("/usr/local/share/applications"),
                Path("/usr/share/applications"), Path.home() / ".local/share/flatpak/exports/share/applications",
                Path("/var/lib/flatpak/exports/share/applications"), Path("/var/lib/snapd/desktop/applications")]
ESPEAK = shutil.which("espeak-ng") or shutil.which("espeak")
ESPEAK_WPM = 165  # words per minute at speed 1.0


def _has_session_bus() -> bool:
    uid = getattr(os, "getuid", lambda: 0)()  # (this module is also imported on Windows by the tests)
    return bool(os.environ.get("DBUS_SESSION_BUS_ADDRESS")) or Path(f"/run/user/{uid}/bus").exists()


def _caps() -> set[str]:
    caps = {"apps", "command", "local_stt"}
    if _has_session_bus():
        caps.add("media_session")
    if shutil.which("pactl"):
        caps.add("mixer")
    if ESPEAK:
        caps.add("offline_voice")
    if shutil.which("curl"):
        caps.add("agent_hooks")
    return caps


CAPS = _caps()


# ----- apps (.desktop files) -----

def _desktop_entry(path: Path) -> dict | None:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        parser.read(path, encoding="utf-8")
    except (configparser.Error, UnicodeDecodeError, OSError):
        return None
    if "Desktop Entry" not in parser:
        return None
    entry = parser["Desktop Entry"]
    if (entry.get("Type") != "Application" or entry.get("NoDisplay", "").lower() == "true"
            or entry.get("Hidden", "").lower() == "true" or not entry.get("Exec")):
        return None
    lang = (os.environ.get("LANG") or "")[:2]
    name = entry.get(f"Name[{lang}]") or entry.get("Name")
    return {"name": name, "id": str(path)} if name else None


def list_apps() -> list[dict]:
    apps: dict[str, dict] = {}
    for folder in DESKTOP_DIRS:
        try:
            files = sorted(folder.glob("*.desktop"))
        except OSError:
            continue
        for path in files:
            if path.name in apps:  # the first folder wins (user entries override system ones)
                continue
            entry = _desktop_entry(path)
            if entry:
                apps[path.name] = entry
    return list(apps.values())


def launch_app(app: dict) -> None:
    path = Path(app["id"])
    if shutil.which("gtk-launch"):
        subprocess.Popen(["gtk-launch", path.stem], start_new_session=True)
    else:
        subprocess.Popen(["gio", "launch", str(path)], start_new_session=True)


def open_path(path: str) -> None:
    subprocess.Popen(["xdg-open", path], start_new_session=True)


def reveal(path: str) -> None:
    subprocess.Popen(["xdg-open", str(Path(path).parent)], start_new_session=True)


def pick_folder(initial: str) -> str | None:
    if not shutil.which("zenity"):
        return None
    start = initial if os.path.isdir(initial) else str(Path.home())
    out = subprocess.run(["zenity", "--file-selection", "--directory", "--title=Carpeta que Elissa puede leer",
                          f"--filename={start.rstrip('/')}/"], capture_output=True, text=True)
    return out.stdout.strip() or None


def press_media_key(vk: int) -> bool:
    return False  # no key injection on Linux: playback goes through MPRIS (media_control)


# ----- music (MPRIS over D-Bus) -----

MPRIS = "org.mpris.MediaPlayer2."


def _bus(kind: str = "SESSION"):
    from jeepney.io.blocking import open_dbus_connection
    return open_dbus_connection(bus=kind)


def _players(conn) -> list[str]:
    from jeepney import DBusAddress, new_method_call
    dbus = DBusAddress("/org/freedesktop/DBus", bus_name="org.freedesktop.DBus", interface="org.freedesktop.DBus")
    names = conn.send_and_get_reply(new_method_call(dbus, "ListNames")).body[0]
    return sorted((n for n in names if n.startswith(MPRIS)), key=lambda n: "spotify" not in n.lower())


def _player(name: str):
    from jeepney import DBusAddress
    return DBusAddress("/org/mpris/MediaPlayer2", bus_name=name, interface="org.mpris.MediaPlayer2.Player")


def _prop(conn, address, prop: str):
    from jeepney import Properties
    return conn.send_and_get_reply(Properties(address).get(prop)).body[0][1]


def parse_metadata(meta: dict, status: str, player: str) -> dict | None:
    """MPRIS Metadata ({key: (signature, value)}) to {title, artist, album, playing, player}."""
    def value(key):
        return meta.get(key, ("s", ""))[1]
    title = value("xesam:title")
    if not title:
        return None
    artist = value("xesam:artist")
    return {"title": title, "artist": ", ".join(artist) if isinstance(artist, list) else artist,
            "album": value("xesam:album") or "", "playing": status == "Playing", "player": player}


def _player_label(name: str) -> str:
    base = name.removeprefix(MPRIS).split(".")[0]
    return "Spotify" if base.lower() == "spotify" else base.capitalize()


def media_now_playing() -> dict | None:
    try:
        with _bus() as conn:
            found = []
            for name in _players(conn):
                addr = _player(name)
                info = parse_metadata(_prop(conn, addr, "Metadata"), _prop(conn, addr, "PlaybackStatus"),
                                      _player_label(name))
                if info:
                    found.append(info)
    except Exception:
        return None
    return next((i for i in found if i["playing"]), found[0] if found else None)


MPRIS_METHODS = {"toggle": "PlayPause", "play": "Play", "pause": "Pause", "next": "Next", "previous": "Previous"}


def media_control(action: str) -> bool | None:
    from jeepney import new_method_call
    try:
        with _bus() as conn:
            players = _players(conn)
            if not players:
                return None
            playing = [p for p in players if _prop(conn, _player(p), "PlaybackStatus") == "Playing"]
            conn.send_and_get_reply(new_method_call(_player((playing or players)[0]), MPRIS_METHODS[action]))
            return True
    except Exception:
        return None


# ----- volume and ducking (pactl: PulseAudio or PipeWire) -----

def _pactl(*args: str) -> str:
    return subprocess.run(["pactl", *args], capture_output=True, text=True, timeout=5).stdout


def get_volume() -> dict:
    m = re.search(r"(\d+)%", _pactl("get-sink-volume", "@DEFAULT_SINK@"))
    return {"percent": int(m.group(1)) if m else 0, "muted": "yes" in _pactl("get-sink-mute", "@DEFAULT_SINK@")}


def set_volume(percent: int | None, delta: int | None, mute: bool | None) -> dict:
    if percent is not None or delta is not None:
        target = percent if percent is not None else get_volume()["percent"] + delta
        _pactl("set-sink-volume", "@DEFAULT_SINK@", f"{max(0, min(100, int(target)))}%")
        if mute is None:
            _pactl("set-sink-mute", "@DEFAULT_SINK@", "0")
    if mute is not None:
        _pactl("set-sink-mute", "@DEFAULT_SINK@", "1" if mute else "0")
    return get_volume()


def parse_sink_inputs(data: list) -> list[dict]:
    """`pactl -f json list sink-inputs` to [{"index", "pid", "volume" (percent), "playing"}]."""
    out = []
    for s in data:
        channels = list((s.get("volume") or {}).values())
        if not channels:
            continue
        percent = int(str(channels[0].get("value_percent", "0")).rstrip("%") or 0)
        pid = (s.get("properties") or {}).get("application.process.id")
        out.append({"index": s["index"], "pid": int(pid) if str(pid).isdigit() else 0, "volume": percent,
                    "playing": not s.get("corked", False)})
    return out


def sink_inputs() -> list[dict]:
    try:
        return parse_sink_inputs(json.loads(_pactl("-f", "json", "list", "sink-inputs") or "[]"))
    except ValueError:
        return []


def set_sink_input_volume(index: int, percent: int) -> None:
    _pactl("set-sink-input-volume", str(index), f"{max(0, min(150, int(percent)))}%")


# ----- offline voice (espeak-ng) -----

def espeak_voices() -> list[dict]:
    if not ESPEAK:
        return []
    out = subprocess.run([ESPEAK, "--voices"], capture_output=True, text=True, timeout=10).stdout
    return parse_espeak_voices(out)


def parse_espeak_voices(out: str) -> list[dict]:
    voices = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 4 and parts[0].isdigit():
            voices.append({"name": parts[3].replace("_", " "), "lang": parts[1], "id": parts[1]})
    return voices


def espeak_synthesize(text: str, voice: str = "", speed: float = 1.0) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "espeak.wav")
        cmd = [ESPEAK, "-s", str(int(ESPEAK_WPM * speed)), "-w", path]
        if voice:
            cmd += ["-v", voice]
        subprocess.run(cmd + ["--", text], check=True, capture_output=True, timeout=60)
        return Path(path).read_bytes()


# ----- session -----

def session_locked() -> bool:
    """logind's LockedHint for this session (desktops that lock through logind set it)."""
    try:
        from jeepney import DBusAddress, Properties
        session = DBusAddress("/org/freedesktop/login1/session/auto", bus_name="org.freedesktop.login1",
                              interface="org.freedesktop.login1.Session")
        with _bus("SYSTEM") as conn:
            return bool(conn.send_and_get_reply(Properties(session).get("LockedHint")).body[0][1])
    except Exception:
        return False


# ----- Spotify desktop, child processes -----

def spotify_installed() -> bool:
    return bool(shutil.which("spotify")) or any(
        (d / "com.spotify.Client.desktop").exists() or (d / "spotify.desktop").exists() for d in DESKTOP_DIRS)


def launch_spotify() -> None:
    if shutil.which("spotify"):
        subprocess.Popen(["spotify"], start_new_session=True)
    else:
        subprocess.Popen(["xdg-open", "spotify:"], start_new_session=True)


class ChildGuard:
    """Children get SIGTERM when the engine dies (prctl PR_SET_PDEATHSIG), set when they start."""

    @staticmethod
    def preexec() -> None:
        try:
            ctypes.CDLL("libc.so.6").prctl(1, signal.SIGTERM)  # PR_SET_PDEATHSIG
        except OSError:
            pass

    def add(self, proc: subprocess.Popen) -> None:
        pass
