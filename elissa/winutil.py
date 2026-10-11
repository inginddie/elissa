"""Small Win32 helpers: folder picker and waiting for the desktop shell process to exit."""
import ctypes
import subprocess
from ctypes import wintypes

kernel32 = ctypes.windll.kernel32
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

SYNCHRONIZE = 0x00100000
INFINITE = 0xFFFFFFFF


def wait_for_exit(pid: int) -> None:
    """Blocks until the process exits (returns at once if it is already gone)."""
    handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        return
    try:
        kernel32.WaitForSingleObject(handle, INFINITE)
    finally:
        kernel32.CloseHandle(handle)


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
    path = out.stdout.strip()
    return path or None
