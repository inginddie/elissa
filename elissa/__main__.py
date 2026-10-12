"""Engine entry point (also the PyInstaller target `elissa-engine.exe`).

Normally started by the desktop shell (Tauri), which passes ELISSA_PORT, ELISSA_TOKEN and ELISSA_PARENT_PID and
shows the UI in its own window. Run by hand (`uv run python -m elissa --browser`) it opens the UI in the default
browser instead, which is handy for development.
"""
import logging
import os
import secrets
import sys
import threading
import time
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path

import uvicorn

from elissa.config import LOG_DIR, migrate_legacy_home


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LOG_DIR / "elissa.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    if sys.stderr:  # running from a console (dev)
        root.addHandler(logging.StreamHandler())
    for noisy in ("httpx", "httpcore", "openai", "anthropic", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def selftest() -> int:
    """`elissa-engine --selftest`: checks that the bundle ships everything the tools need on this system."""
    import asyncio
    import tempfile

    import docx

    from elissa import system
    from elissa.config import get_secret, set_secret
    from elissa.tools.files import extract_text
    from elissa.tools.web import web_search

    checks = {}

    def check(name, fn):
        try:
            checks[name] = f"ok ({fn()})"
        except Exception as e:  # report every failure, don't stop at the first
            checks[name] = f"FALLA: {e!r}"

    def synth():
        """Edge's online voice (with its host fallback); the system's offline voice is the fallback in the app too."""
        from elissa import edge_voice, offline_voice
        try:
            return f"Edge, {len(asyncio.run(edge_voice.synthesize('Hola', 'es-CO-SalomeNeural')))} bytes"
        except Exception as e:
            if not system.has("offline_voice"):
                raise
            wav = offline_voice.synthesize("Hola", "", 1.0)
            return f"Edge no disponible ({str(e)[:60]}); voz del sistema, {len(wav)} bytes"

    def roundtrip():
        set_secret("selftest", "x")
        ok = get_secret("selftest") == "x"
        set_secret("selftest", "")
        return "credenciales" if ok else 1 / 0

    def office():
        path = Path(tempfile.mkdtemp()) / "t.docx"
        d = docx.Document()
        d.add_paragraph("prueba elissa")
        d.save(path)
        return extract_text(path).strip()

    def microphone():
        import sounddevice
        import vosk  # noqa: F401  (wake phrase engine is bundled)
        return f"{len([d for d in sounddevice.query_devices() if d['max_input_channels'] > 0])} entradas de audio"

    def integrations():
        from mcp import ClientSession  # noqa: F401
        from mcp.client.stdio import stdio_client  # noqa: F401
        from mcp.client.streamable_http import streamable_http_client  # noqa: F401
        return "cliente MCP"

    def media():
        import winrt.windows.foundation  # noqa: F401  (needed at runtime by the media controls)
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager  # noqa: F401
        import psutil  # noqa: F401  (finds Elissa's own processes so ducking skips them)
        from pycaw.pycaw import AudioUtilities  # noqa: F401  (volume and ducking)
        return "controles multimedia y volumen de Windows"

    def offline():
        from elissa import offline_voice
        voices = offline_voice.list_voices("es") + offline_voice.list_voices("en")
        wav = offline_voice.synthesize("Hola", voices[0]["id"] if voices else "", 1.0)
        return f"{len(voices)} voces, {len(wav)} bytes"

    def windows():
        import uiautomation as auto
        return f"{len(auto.GetRootControl().GetChildren())} ventanas"

    check("busqueda_web", lambda: f"{web_search('Bogotá', 2).count(chr(10))} líneas")
    check("voz", synth)
    if os.getenv("ELISSA_SELFTEST_NO_KEYRING"):  # CI on Linux has no Secret Service running
        checks["keyring"] = "ok (omitido: sin llavero en este entorno)"
    else:
        check("keyring", roundtrip)
    check("documentos", office)
    if system.has("computer_use"):
        check("ventanas", windows)
    check("microfono", microphone)
    check("integraciones", integrations)
    if system.has("mixer") and system.IS_WINDOWS:
        check("multimedia", media)
    if system.has("offline_voice"):
        check("voz_sin_conexion", offline)
    checks["sistema"] = f"ok ({system.NAME}: {', '.join(sorted(system.CAPS)) or 'básico'})"
    for name, result in checks.items():
        logging.info("selftest %s: %s", name, result)
    (LOG_DIR / "selftest.txt").write_text("\n".join(f"{k}: {v}" for k, v in checks.items()), "utf-8")
    return 0 if all(v.startswith("ok") for v in checks.values()) else 1


def main() -> None:
    migrate_legacy_home()  # before logging opens a file in the data folder
    setup_logging()
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    port = int(os.getenv("ELISSA_PORT", "8740"))
    # The server reads the token from the environment; set it before importing it.
    token = os.environ.setdefault("ELISSA_TOKEN", secrets.token_hex(16))

    from elissa.server import app
    # Long ping timeout: with a local model maxing out the CPU, pongs can be late.
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None, log_level="warning",
                                           ws_ping_interval=30, ws_ping_timeout=120))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    logging.info("Elissa engine listening on 127.0.0.1:%s", port)
    if "--browser" in sys.argv:
        webbrowser.open(f"http://127.0.0.1:{port}/?t={token}")
    thread.join()


if __name__ == "__main__":
    main()
