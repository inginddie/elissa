"""Screenshots of Elissa's window for the wiki, in Spanish and English, into docs/media/screens/<lang>/.

    uv run --with playwright==1.63.0 python scripts/wiki_screenshots.py

Starts the real engine with a throwaway data folder, home folder and an empty keyring, so nothing of yours shows up,
and drives the UI with Microsoft Edge (installed with Windows; no browser download). The window sizes match the
desktop shell's modes. Approval cards and the reply are injected into the page as if the engine had sent them, so no
AI provider is needed.
"""

import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "media" / "screens"
PORT = 8790

# Window sizes of the desktop shell's modes (desktop/src-tauri/src/lib.rs). Short cards are shot shorter than their
# window, so the picture has no empty space.
COMPACT, TALK, PANEL = (168, 188), (360, 330), (400, 640)
SHORT = (400, 430)

# Pretends to be the desktop shell (so "Start with the system" shows) and lets the script inject engine messages and
# hold back the typed question, which would otherwise go to an AI provider.
INIT = """
window.__TAURI__ = {
  core: { invoke: async (cmd) => ({ get_autostart: true, shell_info: { update: null } })[cmd] ?? null },
  event: { listen: async () => () => {} },
  window: { getCurrentWindow: () => ({ startDragging: async () => {} }) },
};
const NativeWS = window.WebSocket;
window.WebSocket = class extends NativeWS {
  constructor(...a) { super(...a); window.__ws = this; }
  send(d) { if (!String(d).includes('"type": "text"') && !String(d).includes('"type":"text"')) super.send(d); }
};
window.__inject = (m) => window.__ws.onmessage({ data: JSON.stringify(m) });
"""

TEXT = {
    "es": {
        "language": "es-CO", "voice": "es-CO-SalomeNeural",
        "folders": ["C:\\Users\\Ana\\Documents", "D:\\Proyectos"],
        "question": "¿Qué tengo pendiente hoy?",
        "reply": "Tienes dos tareas: comprar pan y llamar a Ana a las 3. ¿Te pongo un recordatorio?",
        "diff": {"title": "Editar un archivo", "kind": "diff", "path": "C:\\Users\\Ana\\Documents\\notas.md",
                 "diff": "@@ -1,3 +1,4 @@\n # Lista de compras\n-- leche\n+- leche deslactosada\n+- pan integral\n - café"},
        "email": {"title": "Enviar un correo", "kind": "email", "subtitle": "Desde ana@example.com",
                  "to": "carlos@example.com", "subject": "Reunión del jueves",
                  "body": "Hola Carlos:\n\nConfirmo la reunión del jueves a las 10.\n\nSaludos,\nAna"},
        "command": {"title": "Ejecutar un comando", "kind": "command", "cwd": "D:\\Proyectos\\tienda",
                    "command": "npm test", "subtitle": "Tiempo máximo: 120 s"},
    },
    "en": {
        "language": "en-US", "voice": "en-US-AvaNeural",
        "folders": ["C:\\Users\\Ana\\Documents", "D:\\Projects"],
        "question": "What do I have to do today?",
        "reply": "You have two tasks: buy bread and call Carlos at 3. Shall I set a reminder?",
        "diff": {"title": "Edit a file", "kind": "diff", "path": "C:\\Users\\Ana\\Documents\\notes.md",
                 "diff": "@@ -1,3 +1,4 @@\n # Shopping list\n-- milk\n+- lactose-free milk\n+- whole-grain bread\n - coffee"},
        "email": {"title": "Send an email", "kind": "email", "subtitle": "From ana@example.com",
                  "to": "carlos@example.com", "subject": "Thursday's meeting",
                  "body": "Hi Carlos,\n\nConfirming Thursday's meeting at 10.\n\nBest,\nAna"},
        "command": {"title": "Run a command", "kind": "command", "cwd": "D:\\Projects\\shop",
                    "command": "npm test", "subtitle": "Time limit: 120 s"},
    },
}


def start_engine(lang: str, tmp: Path) -> tuple[subprocess.Popen, str]:
    home, data = tmp / "home", tmp / "data"
    for d in (home / ".claude", home / ".codex", data):
        d.mkdir(parents=True, exist_ok=True)
    t = TEXT[lang]
    (data / "settings.json").write_text(json.dumps({
        "ui_language": lang, "language": t["language"], "voice": t["voice"], "language_autosynced": True,
        "provider": "ollama", "model": "qwen3:4b", "user_name": "Ana", "allowed_folders": t["folders"],
        "mail_enabled": True, "mail_user": "ana@example.com",
        "mcp_servers": [{"id": "github", "name": "GitHub", "transport": "http", "url": "https://api.githubcopilot.com/mcp/",
                         "command": "", "args": [], "enabled": False, "trust_reads": True}],
    }), "utf-8")
    token = secrets.token_hex(16)
    env = {**os.environ, "ELISSA_HOME": str(data), "ELISSA_PORT": str(PORT), "ELISSA_TOKEN": token,
           "USERPROFILE": str(home), "HOME": str(home), "PYTHON_KEYRING_BACKEND": "keyring.backends.null.Keyring"}
    engine = subprocess.Popen([sys.executable, "-m", "elissa"], cwd=ROOT, env=env)
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=1)
            return engine, token
        except urllib.error.HTTPError:  # it answers: it's up
            return engine, token
        except OSError:
            time.sleep(0.3)
    engine.kill()
    engine.wait(10)
    raise RuntimeError("the engine didn't start")


def shoot(lang: str, browser, token: str) -> None:
    out = OUT / lang
    out.mkdir(parents=True, exist_ok=True)
    t = TEXT[lang]
    url = f"http://127.0.0.1:{PORT}/?t={token}"

    def page_at(size, hash_=""):
        ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, device_scale_factor=2,
                                  permissions=["microphone"])
        ctx.add_init_script(INIT)
        page = ctx.new_page()
        page.goto(url + hash_)
        page.wait_for_function("document.body.dataset.state !== 'waking'", timeout=20000)
        page.wait_for_timeout(1500)  # the greeting animation
        return page

    def save(page, name, wait=600):
        page.wait_for_timeout(wait)
        page.screenshot(path=str(out / f"{name}.png"), omit_background=True)
        print("  ", lang, name)

    # Resting on the desktop.
    page = page_at(COMPACT)
    save(page, "compact", 2500)
    page.context.close()

    # Listening, with the fake microphone.
    page = page_at(TALK)
    page.click("#face")
    save(page, "listening", 900)
    page.context.close()

    # A typed question and her answer.
    page = page_at(TALK)
    page.evaluate("document.querySelector('#btn-history').click()")
    page.fill("#typed", t["question"])
    page.press("#typed", "Enter")
    page.evaluate("""([reply]) => {
        __inject({ type: 'turn', turn: 999 });
        __inject({ type: 'delta', turn: 999, text: reply });
        __inject({ type: 'say', turn: 999, text: reply });  // her real voice, so she's speaking in the picture
    }""", [t["reply"]])
    page.wait_for_function("document.body.dataset.state === 'speaking'", timeout=20000)
    save(page, "reply", 1500)
    page.evaluate("__inject({ type: 'done', turn: 999 })")
    page.context.close()

    # Approval cards.
    for name, size in (("diff", SHORT), ("email", SHORT), ("command", (400, 340))):
        page = page_at(size)
        page.evaluate("(card) => __inject({ type: 'approval', id: 'shot', turn: 0, tool: 'x', ...card })", t[name])
        save(page, f"approval-{name}", 900)
        page.context.close()

    # Setting up the AI, with a provider that needs a key.
    page = page_at(SHORT, "#configurar")
    page.select_option("#setup-provider", "groq")
    save(page, "setup")
    page.context.close()

    # Settings, one screenshot per section (scrolled so its heading is at the top).
    page = page_at(PANEL, "#ajustes")
    page.wait_for_timeout(2500)  # voices, integrations and alerts load
    # Index of the section's heading; each picture also shows the start of the next ones.
    sections = {"settings-general": 0, "settings-voice": 2, "settings-email": 4, "settings-mcp": 5,
                "settings-spotify": 6, "settings-alerts": 7}
    for name, index in sections.items():
        page.evaluate("""(i) => {
            const h = document.querySelectorAll('#settings h3')[i];
            const box = document.querySelector('#settings');
            box.scrollTop = h.offsetTop - box.offsetTop - 8;
        }""", index)
        save(page, name, 400)
    page.context.close()


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", args=[
            "--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required"])
        for lang in ("es", "en"):
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
                engine, token = start_engine(lang, Path(tmp))
                try:
                    shoot(lang, browser, token)
                finally:
                    engine.terminate()
                    engine.wait(10)
        browser.close()


if __name__ == "__main__":
    main()
