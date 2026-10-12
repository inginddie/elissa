"""The system module: one interface on every OS, capabilities declared per system."""
import subprocess
import sys

from elissa import system


def test_interface_and_capabilities():
    assert system.NAME in ("windows", "macos", "linux")
    for fn in ("list_apps", "launch_app", "open_path", "reveal", "pick_folder", "press_media_key", "session_locked",
               "spotify_installed", "launch_spotify", "wait_for_exit"):
        assert callable(getattr(system, fn))
    assert system.CAPS <= {"apps", "media_session", "media_keys", "mixer", "offline_voice", "local_stt",
                           "computer_use", "command", "agent_hooks"}
    if system.IS_WINDOWS:
        assert system.has("computer_use") and system.has("mixer")


def test_wait_for_exit():
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    system.wait_for_exit(proc.pid)  # returns once it ends
    proc.wait()
    system.wait_for_exit(proc.pid)  # already gone: returns at once
