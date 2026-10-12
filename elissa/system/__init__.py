"""What depends on the operating system, behind one interface: Windows, macOS and Linux.

Tools only talk to this module. Each system module provides the same functions; what a system can't do is left out of
CAPS, and the tool that would need it is not registered (better than a tool that always fails).

Capabilities:
- apps: list and open installed apps
- media_session: what is playing / play-pause-next on one player
- media_keys: system media keys
- mixer: system volume and lowering other apps (ducking)
- offline_voice: a voice that works without internet
- local_stt: on-PC speech recognition (whisper.cpp build available)
- computer_use: read other windows, click, type
- command: run shell commands in a project
- agent_hooks: alerts from Claude Code / Codex hooks
"""
import subprocess
import sys

import psutil

IS_WINDOWS = sys.platform == "win32"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # creationflags: no console window for child processes
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
NAME = "windows" if IS_WINDOWS else "macos" if IS_MAC else "linux"

if IS_WINDOWS:
    from .windows import (CAPS, ChildGuard, launch_app, list_apps, open_path, pick_folder, press_media_key, reveal,
                          session_locked, spotify_installed, launch_spotify)
elif IS_MAC:
    from .macos import (CAPS, ChildGuard, launch_app, list_apps, media_control, media_now_playing, open_path,
                        pick_folder, press_media_key, reveal, session_locked, spotify_installed, launch_spotify)
else:
    from .linux import (CAPS, ChildGuard, launch_app, list_apps, media_control, media_now_playing, open_path,
                        pick_folder, press_media_key, reveal, session_locked, spotify_installed, launch_spotify)

__all__ = ["CAPS", "IS_LINUX", "IS_MAC", "IS_WINDOWS", "NAME", "NO_WINDOW", "ChildGuard", "has", "launch_app",
           "launch_spotify", "list_apps", "open_path", "pick_folder", "press_media_key", "reveal", "session_locked",
           "spotify_installed", "wait_for_exit"]
# media_now_playing / media_control exist on macOS and Linux; Windows uses its media controls in media_session.


def has(capability: str) -> bool:
    return capability in CAPS


def wait_for_exit(pid: int) -> None:
    """Blocks until the process exits (returns at once if it is already gone)."""
    try:
        psutil.Process(pid).wait()
    except psutil.NoSuchProcess:
        return
