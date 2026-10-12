"""Everyday actions that don't need approval: open web pages, apps, files and folders, and control media playback.

Nothing here runs arbitrary programs: apps come from the Start menu (Get-StartApps), files must be inside the
allowed folders and executables/scripts are never opened.
"""
import ctypes
import difflib
import json
import os
import subprocess
import time
import unicodedata
import webbrowser
from urllib.parse import urlparse

from .. import media_session
from . import ToolRegistry
from .files import FileTools

BLOCKED_EXT = {".exe", ".bat", ".cmd", ".com", ".ps1", ".psm1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh",
               ".msi", ".msp", ".scr", ".pif", ".lnk", ".url", ".jar", ".reg", ".hta", ".cpl", ".inf", ".appref-ms"}
APPS_TTL_S = 600
# Common names people say that differ from the Start menu entry (Spanish Windows names first).
APP_ALIASES = {
    "vs code": ["visual studio code"], "vscode": ["visual studio code"], "code": ["visual studio code"],
    "notepad": ["bloc de notas", "notepad"], "calculator": ["calculadora", "calculator"],
    "settings": ["configuracion", "settings"], "ajustes": ["configuracion"],
    "explorer": ["explorador de archivos", "file explorer"], "explorador": ["explorador de archivos"],
    "chrome": ["google chrome"], "word": ["word"], "terminal": ["terminal", "windows terminal"],
    "correo": ["outlook", "correo"], "calendario": ["outlook", "calendario"], "camara": ["camara", "camera"],
}

# Virtual-key codes for the media keys every Windows player listens to.
MEDIA_KEYS = {"pausa": 0xB3, "reproducir": 0xB3, "siguiente": 0xB0, "anterior": 0xB1, "detener": 0xB2,
              "silencio": 0xAD, "bajar_volumen": 0xAE, "subir_volumen": 0xAF}
KEYEVENTF_KEYUP = 0x0002
SESSION_ACTIONS = {"pausa": "pause", "reproducir": "play", "siguiente": "next", "anterior": "previous"}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c)).strip()


class Actions:
    def __init__(self, files: FileTools):
        self.files = files
        self._apps: list[dict] = []
        self._apps_at = 0.0

    # ----- web -----

    def open_web(self, url: str) -> str:
        url = url.strip()
        if "://" not in url:
            url = "https://" + url
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("Solo abro direcciones web (http o https).")
        webbrowser.open(url)
        return f"Abrí {parsed.netloc} en el navegador."

    # ----- apps -----

    def start_apps(self) -> list[dict]:
        """Name and AppID of every app in the Start menu (desktop and Store apps alike), cached for a while."""
        if not self._apps or time.time() - self._apps_at > APPS_TTL_S:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-StartApps | ConvertTo-Json -Compress"],
                capture_output=True, text=True, encoding="utf-8", timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW)
            data = json.loads(out.stdout or "[]")
            self._apps = [data] if isinstance(data, dict) else data
            self._apps_at = time.time()
        return self._apps

    def find_app(self, name: str) -> dict | None:
        apps = self.start_apps()
        wanted = _norm(name)
        by_name = {_norm(a["Name"]): a for a in apps}
        if wanted in by_name:
            return by_name[wanted]
        for alias in APP_ALIASES.get(wanted, []):
            if alias in by_name:
                return by_name[alias]
        starts = [a for n, a in by_name.items() if n.startswith(wanted)]
        if starts:
            return min(starts, key=lambda a: len(a["Name"]))
        contains = [a for n, a in by_name.items() if wanted in n]
        if contains:
            return min(contains, key=lambda a: len(a["Name"]))
        close = difflib.get_close_matches(wanted, list(by_name), n=1, cutoff=0.6)
        return by_name[close[0]] if close else None

    def open_app(self, name: str) -> str:
        app = self.find_app(name)
        if not app:
            raise LookupError(f"No encontré una aplicación llamada {name!r} en el menú Inicio.")
        os.startfile(f"shell:AppsFolder\\{app['AppID']}")
        return f"Abrí {app['Name']}."

    def list_apps(self, filter: str = "") -> str:
        names = sorted({a["Name"] for a in self.start_apps()}, key=str.lower)
        if filter:
            names = [n for n in names if _norm(filter) in _norm(n)]
        return "\n".join(names[:150]) or "No hay aplicaciones que coincidan."

    # ----- files and folders -----

    def open_path(self, path: str) -> str:
        p = self.files.resolve(path)
        if not p.exists():
            raise FileNotFoundError(f"No existe {p}.")
        if p.is_file() and p.suffix.lower() in BLOCKED_EXT:
            raise PermissionError("Por seguridad no abro programas, scripts ni accesos directos.")
        os.startfile(str(p))
        return f"Abrí {p.name or p}."

    def show_in_folder(self, path: str) -> str:
        p = self.files.resolve(path)
        if not p.exists():
            raise FileNotFoundError(f"No existe {p}.")
        subprocess.Popen(["explorer", "/select,", str(p)])
        return f"Te muestro {p.name} en su carpeta."

    # ----- media -----

    async def media(self, action: str, times: int = 1) -> str:
        key = MEDIA_KEYS.get(action)
        if key is None:
            raise ValueError(f"Acción desconocida. Opciones: {', '.join(MEDIA_KEYS)}.")
        times = max(1, min(int(times or 1), 25))
        session_action = SESSION_ACTIONS.get(action)
        if session_action and times == 1:
            # Windows' media controls aim at one player (Spotify first) instead of whichever grabs the keys
            done = await media_session.control(session_action)
            if done is not None:
                return "Listo." if done else "El reproductor no aceptó la orden."
        for _ in range(times):
            ctypes.windll.user32.keybd_event(key, 0, 0, 0)
            ctypes.windll.user32.keybd_event(key, 0, KEYEVENTF_KEYUP, 0)
        return "Listo."


def register(reg: ToolRegistry, actions: Actions) -> None:
    reg.add("abrir_web", "Abre una página web en el navegador predeterminado. Para buscar algo en internet usa "
            "buscar_web; usa esta cuando el usuario quiera VER la página.", "Abriendo la página…",
            actions.open_web, {"url": {"type": "string", "description": "Dirección, p. ej. https://github.com"}},
            ["url"])
    reg.add("abrir_app", "Abre una aplicación instalada por su nombre (como aparece en el menú Inicio: Excel, "
            "Spotify, Calculadora, Configuración, Visual Studio Code…).", "Abriendo la aplicación…",
            actions.open_app, {"name": {"type": "string"}}, ["name"])
    reg.add("listar_apps", "Lista las aplicaciones instaladas (menú Inicio), opcionalmente filtradas por texto.",
            "Revisando tus aplicaciones…", actions.list_apps, {"filter": {"type": "string"}})
    reg.add("abrir_archivo", "Abre un archivo o carpeta con su programa predeterminado (documentos, imágenes, "
            "PDF, carpetas). Acepta alias como 'Descargas'. No abre programas ni scripts.", "Abriendo…",
            actions.open_path, {"path": {"type": "string"}}, ["path"])
    reg.add("mostrar_en_carpeta", "Abre el Explorador de archivos con el archivo seleccionado.",
            "Abriendo el Explorador…", actions.show_in_folder, {"path": {"type": "string"}}, ["path"])
    reg.add("multimedia", "Controla la música o el video que esté sonando y el volumen del sistema.",
            "Ajustando la música…", actions.media,
            {"action": {"type": "string", "enum": list(MEDIA_KEYS)},
             "times": {"type": "integer", "description": "Repeticiones (p. ej. pasos de volumen, por defecto 1)"}},
            ["action"])
