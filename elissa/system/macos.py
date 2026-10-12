"""macOS: apps in the Applications folders, `open`, AppleScript dialogs.

Media, volume and ducking, the offline voice, local speech recognition and computer use arrive in F8.2.
"""
import os
import subprocess
from pathlib import Path

CAPS = {"apps"}

APP_DIRS = [Path("/Applications"), Path("/System/Applications"), Path("/System/Applications/Utilities"),
            Path.home() / "Applications"]


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
    out = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return out.stdout.strip().rstrip("/") or None


def press_media_key(vk: int) -> bool:
    return False  # no public API; media control on macOS goes through the player (F8.2)


def session_locked() -> bool:
    return False  # F8.2: CGSessionCopyCurrentDictionary


def spotify_installed() -> bool:
    return any((d / "Spotify.app").exists() for d in APP_DIRS)


def launch_spotify() -> None:
    subprocess.Popen(["open", "-a", "Spotify"])


class ChildGuard:
    """F8.2: tie child processes to the engine (kqueue). Until then the engine stops them itself on exit."""

    def add(self, proc: subprocess.Popen) -> None:
        pass
