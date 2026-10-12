"""Linux: `xdg-open` and a folder dialog with zenity when it is installed.

Apps (.desktop files), MPRIS media, PipeWire/PulseAudio volume and ducking, the offline voice and the rest arrive in
F8.3.
"""
import ctypes
import os
import shutil
import signal
import subprocess
from pathlib import Path

CAPS: set[str] = set()


def list_apps() -> list[dict]:
    return []


def launch_app(app: dict) -> None:
    raise NotImplementedError


def open_path(path: str) -> None:
    subprocess.Popen(["xdg-open", path])


def reveal(path: str) -> None:
    subprocess.Popen(["xdg-open", str(Path(path).parent)])


def pick_folder(initial: str) -> str | None:
    if not shutil.which("zenity"):
        return None
    start = initial if os.path.isdir(initial) else str(Path.home())
    out = subprocess.run(["zenity", "--file-selection", "--directory", "--title=Carpeta que Elissa puede leer",
                          f"--filename={start.rstrip('/')}/"], capture_output=True, text=True)
    return out.stdout.strip() or None


def press_media_key(vk: int) -> bool:
    return False  # F8.3: MPRIS


def session_locked() -> bool:
    return False  # F8.3: logind LockedHint


def spotify_installed() -> bool:
    return bool(shutil.which("spotify"))


def launch_spotify() -> None:
    subprocess.Popen(["spotify"], start_new_session=True)


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
