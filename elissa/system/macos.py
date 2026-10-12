"""macOS: apps in the Applications folders, `open`, AppleScript for music and volume, `say`, the session lock.

macOS has no per-app volume and no public "now playing" API, so music goes through the players' own AppleScript
(Spotify and Music), only when they are already open, so Elissa never launches one by asking about it.
On-PC speech recognition and computer use arrive later (F8.4).
"""
import ctypes
import os
import re
import subprocess
import tempfile
from pathlib import Path

CAPS = {"apps", "media_session", "mixer", "offline_voice", "command", "agent_hooks"}

APP_DIRS = [Path("/Applications"), Path("/System/Applications"), Path("/System/Applications/Utilities"),
            Path.home() / "Applications"]
PLAYERS = ("Spotify", "Music")  # players Elissa can talk to with AppleScript, in order of preference
SAY_RATE = 185  # words per minute that sound natural at speed 1.0


def _osascript(script: str, timeout: float = 5) -> str:
    out = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    return out.stdout.strip()


def list_apps() -> list[dict]:
    apps = {}
    for folder in APP_DIRS:
        try:
            for entry in folder.iterdir():
                if entry.suffix == ".app":
                    apps.setdefault(entry.stem, {"name": entry.stem, "id": str(entry)})
        except OSError:
            continue
    return list(apps.values())


def launch_app(app: dict) -> None:
    subprocess.Popen(["open", "-a", app["id"]])


def open_path(path: str) -> None:
    subprocess.Popen(["open", path])


def reveal(path: str) -> None:
    subprocess.Popen(["open", "-R", path])


def pick_folder(initial: str) -> str | None:
    start = initial if os.path.isdir(initial) else str(Path.home())
    script = (f'POSIX path of (choose folder with prompt "Carpeta que Elissa puede leer" '
              f'default location (POSIX file "{start.replace(chr(34), "")}"))')
    try:
        return _osascript(script, timeout=600).rstrip("/") or None
    except subprocess.TimeoutExpired:
        return None


def press_media_key(vk: int) -> bool:
    return False  # no public API: playback goes through the players (media_control)


# ----- music -----

def _running(app: str) -> bool:
    return _osascript(f'application "{app}" is running') == "true"


def media_now_playing() -> dict | None:
    """Title, artist, album and state from Spotify or Music (whichever is playing, else the first one open)."""
    found = []
    for app in PLAYERS:
        if not _running(app):
            continue
        out = _osascript(f'''tell application "{app}"
            if player state is stopped then return ""
            set t to current track
            return (name of t) & tab & (artist of t) & tab & (album of t) & tab & (player state as string)
        end tell''')
        info = parse_track(out, app)
        if info:
            found.append(info)
    return next((i for i in found if i["playing"]), found[0] if found else None)


def parse_track(out: str, app: str) -> dict | None:
    parts = out.split("\t")
    if len(parts) != 4 or not parts[0]:
        return None
    return {"title": parts[0], "artist": parts[1], "album": parts[2], "playing": parts[3] == "playing",
            "player": app}


MEDIA_COMMANDS = {"toggle": "playpause", "play": "play", "pause": "pause", "next": "next track",
                  "previous": "previous track"}


def media_control(action: str) -> bool | None:
    """Sends the command to the player that is playing (else the first one open); None if none is open."""
    open_apps = [a for a in PLAYERS if _running(a)]
    if not open_apps:
        return None
    playing = [a for a in open_apps if _osascript(f'tell application "{a}" to return player state as string')
               == "playing"]
    app = (playing or open_apps)[0]
    _osascript(f'tell application "{app}" to {MEDIA_COMMANDS[action]}')
    return True


# ----- volume and ducking (the players' own volume: macOS has no per-app volume) -----

def get_volume() -> dict:
    out = _osascript("set s to get volume settings\nreturn (output volume of s as string) & tab & "
                     "(output muted of s as string)")
    percent, muted = (out.split("\t") + ["", ""])[:2]
    return {"percent": int(percent or 0), "muted": muted == "true"}


def set_volume(percent: int | None, delta: int | None, mute: bool | None) -> dict:
    if percent is not None or delta is not None:
        target = percent if percent is not None else get_volume()["percent"] + delta
        _osascript(f"set volume output volume {max(0, min(100, int(target)))}")
        if mute is None:
            _osascript("set volume output muted false")
    if mute is not None:
        _osascript(f"set volume output muted {'true' if mute else 'false'}")
    return get_volume()


def playing_players() -> dict[str, int]:
    """The players that are playing right now, with their own volume (0-100)."""
    out = {}
    for app in PLAYERS:
        if _running(app):
            state = _osascript(f'tell application "{app}" to return (player state as string) & tab & '
                               f'(sound volume as string)')
            parts = state.split("\t")
            if len(parts) == 2 and parts[0] == "playing" and parts[1].isdigit():
                out[app] = int(parts[1])
    return out


def player_volume(app: str) -> int | None:
    if not _running(app):
        return None
    out = _osascript(f'tell application "{app}" to return sound volume as string')
    return int(out) if out.isdigit() else None


def set_player_volume(app: str, volume: int) -> None:
    _osascript(f'tell application "{app}" to set sound volume to {max(0, min(100, int(volume)))}')


# ----- offline voice (say) -----

VOICE_LINE = re.compile(r"^(.+?)\s+([a-z]{2,3}[_-][A-Za-z0-9]+)\s+#")


def say_voices() -> list[dict]:
    """The system voices: [{"name", "lang"}] (lang like es_ES)."""
    out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=10).stdout
    return parse_voices(out)


def parse_voices(out: str) -> list[dict]:
    voices = []
    for line in out.splitlines():
        m = VOICE_LINE.match(line)
        if m:
            voices.append({"name": m.group(1).strip(), "lang": m.group(2).replace("-", "_")})
    return voices


def say_synthesize(text: str, name: str = "", speed: float = 1.0) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "say.wav")
        cmd = ["say", "-r", str(int(SAY_RATE * speed)), "--file-format=WAVE", "--data-format=LEI16@22050", "-o", path]
        if name:
            cmd += ["-v", name]
        subprocess.run(cmd + ["--", text], check=True, capture_output=True, timeout=60)
        return Path(path).read_bytes()


# ----- session -----

def session_locked() -> bool:
    """True while the screen is locked (CGSSessionScreenIsLocked in the current session's dictionary)."""
    try:
        cg = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    except OSError:
        return False
    cg.CGSessionCopyCurrentDictionary.restype = ctypes.c_void_p
    cf.CFStringCreateWithCString.restype = ctypes.c_void_p
    cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
    cf.CFDictionaryGetValue.restype = ctypes.c_void_p
    cf.CFDictionaryGetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    cf.CFBooleanGetValue.restype = ctypes.c_bool
    cf.CFBooleanGetValue.argtypes = [ctypes.c_void_p]
    cf.CFRelease.argtypes = [ctypes.c_void_p]
    session = cg.CGSessionCopyCurrentDictionary()
    if not session:
        return True  # no GUI session (login window)
    key = cf.CFStringCreateWithCString(None, b"CGSSessionScreenIsLocked", 0x08000100)  # UTF-8
    try:
        value = cf.CFDictionaryGetValue(session, key)
        return bool(value) and cf.CFBooleanGetValue(value)
    finally:
        cf.CFRelease(key)
        cf.CFRelease(session)


# ----- Spotify desktop, child processes -----

def spotify_installed() -> bool:
    return any((d / "Spotify.app").exists() for d in APP_DIRS)


def launch_spotify() -> None:
    subprocess.Popen(["open", "-a", "Spotify"])


class ChildGuard:
    """On-PC speech recognition isn't available on macOS yet (F8.4), so there are no children to tie."""

    def add(self, proc: subprocess.Popen) -> None:
        pass
