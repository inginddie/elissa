"""Windows: Start menu apps, the shell, media keys, the session lock and job objects."""
import ctypes
import json
import os
import subprocess
import winreg
from ctypes import wintypes

CAPS = {"apps", "media_session", "media_keys", "mixer", "offline_voice", "local_stt", "computer_use", "command",
        "agent_hooks"}

KEYEVENTF_KEYUP = 0x0002


def list_apps() -> list[dict]:
    """Every app in the Start menu (desktop and Store apps alike): [{"name", "id"}]."""
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-StartApps | ConvertTo-Json -Compress"],
        capture_output=True, text=True, encoding="utf-8", timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    data = json.loads(out.stdout or "[]")
    data = [data] if isinstance(data, dict) else data
    return [{"name": a["Name"], "id": a["AppID"]} for a in data]


def launch_app(app: dict) -> None:
    os.startfile(f"shell:AppsFolder\\{app['id']}")


def open_path(path: str) -> None:
    os.startfile(path)


def reveal(path: str) -> None:
    subprocess.Popen(["explorer", "/select,", path])


def pick_folder(initial: str) -> str | None:
    script = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
        "$d.Description = 'Carpeta que Elissa puede leer';"
        f"$d.SelectedPath = '{initial.replace(chr(39), chr(39) * 2)}';"
        "$f = New-Object System.Windows.Forms.Form -Property @{TopMost=$true};"
        "if ($d.ShowDialog($f) -eq 'OK') { [Console]::OutputEncoding=[Text.Encoding]::UTF8; $d.SelectedPath }"
    )
    out = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", script],
                         capture_output=True, text=True, encoding="utf-8",
                         creationflags=subprocess.CREATE_NO_WINDOW)
    return out.stdout.strip() or None


def press_media_key(vk: int) -> bool:
    user32 = ctypes.windll.user32
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    return True


def session_locked() -> bool:
    """True while the Windows session is locked (the input desktop can't be opened)."""
    user32 = ctypes.windll.user32
    desk = user32.OpenInputDesktop(0, False, 0x0100)  # DESKTOP_SWITCHDESKTOP
    if not desk:
        return True
    try:
        return not user32.SwitchDesktop(desk)
    finally:
        user32.CloseDesktop(desk)


def spotify_installed() -> bool:
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "spotify"))
        return True
    except OSError:
        return False


def launch_spotify() -> None:
    os.startfile("spotify:")


class ChildGuard:
    """A Windows job object that kills its processes when the engine exits (even if it crashes)."""

    def __init__(self):
        k = ctypes.windll.kernel32
        self.handle = k.CreateJobObjectW(None, None)

        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class Io(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in ("Read", "Write", "Other", "ReadT", "WriteT", "OtherT")]

        class Extended(ctypes.Structure):
            _fields_ = [("Basic", Basic), ("Io", Io), ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        info = Extended()
        info.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        k.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info))

    def add(self, proc: subprocess.Popen) -> None:
        ctypes.windll.kernel32.AssignProcessToJobObject(self.handle, int(proc._handle))
