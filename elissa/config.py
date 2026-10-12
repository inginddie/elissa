"""Paths, settings and secrets.

Everything the app writes lives in %APPDATA%\\Elissa (override with ELISSA_HOME for tests), apart from the
program itself, which the installer puts in %LOCALAPPDATA%\\Elissa: uninstalling never touches the user's memory.
API keys and the mail password never touch disk: they go to the Windows Credential Manager via keyring.
"""
import json
import os
import shutil
import sys
from pathlib import Path

import keyring

APP_NAME = "Elissa"
KEYRING_SERVICE = "Elissa"

HOME = Path(os.getenv("ELISSA_HOME") or Path(os.getenv("APPDATA", Path.home())) / APP_NAME)
# v0.1 kept its data where the program is installed now.
LEGACY_HOME = Path(os.getenv("LOCALAPPDATA", Path.home())) / APP_NAME


def migrate_legacy_home() -> None:
    if os.getenv("ELISSA_HOME") or HOME.exists():
        return
    items = [LEGACY_HOME / name for name in ("settings.json", "memoria", "logs")]
    if not any(p.exists() for p in items):
        return
    HOME.mkdir(parents=True, exist_ok=True)
    for p in items:
        if p.exists():
            shutil.move(str(p), str(HOME / p.name))


SETTINGS_FILE = HOME / "settings.json"
LOG_DIR = HOME / "logs"
SOUNDS_DIR = HOME / "sounds"  # the user's replacements for the built-in sounds
DOWNLOADS = Path.home() / "Downloads"

# Static files live next to the package, or inside the PyInstaller bundle when frozen.
BUNDLE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
STATIC = BUNDLE / "elissa" / "static"

DEFAULTS = {
    "name": "Elissa",
    "user_name": "",
    # LLM
    "provider": "",            # empty until the first-run wizard is completed
    "model": "",
    "base_url": "",            # only for the "custom" provider
    "context_budget": 30000,   # tokens of history before compacting older turns
    # voice
    "voice": "es-CO-SalomeNeural",
    "speed": 1.1,
    "stt": "auto",             # auto | openai | groq | local | endpoint (auto: a cloud key, else endpoint, else local)
    "stt_local_model": "base", # whisper.cpp model when stt == local: base | small
    "stt_url": "",             # OpenAI-compatible /audio/transcriptions endpoint when stt == endpoint
    "language": "es-CO",
    # behaviour
    "continuous": True,
    "wake_word": False,
    "barge_in": False,         # talking over Elissa interrupts her (best with headphones)        # « Hola Elissa »: local wake phrase (keeps the microphone open)
    "pinned": True,
    "sounds": True,
    "sound_volume": 0.6,
    "allowed_folders": [str(Path.home())],
    "computer_use": True,
    "mcp_servers": [],         # integrations: [{id, name, transport: stdio|http, command, args, url, enabled, trust_reads}]      # see, focus and act on other windows (reading and acting always need approval)
    # mail (IMAP to read, SMTP to send)
    "mail_enabled": False,
    "mail_send": False,        # sending is a separate opt-in; every message still needs approval
    "mail_server": "",
    "mail_user": "",
}


def load_settings() -> dict:
    settings = dict(DEFAULTS)
    if SETTINGS_FILE.exists():
        stored = json.loads(SETTINGS_FILE.read_text("utf-8"))
        settings.update({k: v for k, v in stored.items() if k in DEFAULTS})
    if settings["stt"] not in ("auto", "openai", "groq", "local", "endpoint"):  # v0.1 used Edge's recognizer
        settings["stt"] = "endpoint" if settings["stt_url"] else "auto"
    return settings


def save_settings(settings: dict) -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2, ensure_ascii=False), "utf-8")


def get_secret(name: str) -> str:
    try:
        return keyring.get_password(KEYRING_SERVICE, name) or ""
    except Exception:
        return ""


def set_secret(name: str, value: str) -> None:
    if value:
        keyring.set_password(KEYRING_SERVICE, name, value)
    else:
        try:
            keyring.delete_password(KEYRING_SERVICE, name)
        except Exception:
            pass


def api_key_name(provider: str) -> str:
    return f"api_key:{provider}"
