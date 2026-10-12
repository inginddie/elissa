"""Everyday actions that don't need approval: open web pages, apps, files and folders, and control media playback.

Nothing here runs arbitrary programs: apps come from the Start menu (Get-StartApps), files must be inside the
allowed folders and executables/scripts are never opened.
"""
import difflib
import time
import unicodedata
import webbrowser
from urllib.parse import urlparse

from .. import media_session, system
from . import ToolRegistry
from .files import FileTools

BLOCKED_EXT = {".exe", ".bat", ".cmd", ".com", ".ps1", ".psm1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh",
               ".msi", ".msp", ".scr", ".pif", ".lnk", ".url", ".jar", ".reg", ".hta", ".cpl", ".inf", ".appref-ms",
               # macOS and Linux
               ".app", ".command", ".sh", ".bash", ".zsh", ".pkg", ".dmg", ".appimage", ".desktop", ".run", ".deb",
               ".rpm", ".py", ".pl", ".rb"}
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
        """Name and id of every installed app (Start menu, Applications folder…), cached for a while."""
        if not self._apps or time.time() - self._apps_at > APPS_TTL_S:
            self._apps = system.list_apps()
            self._apps_at = time.time()
        return self._apps

    def find_app(self, name: str) -> dict | None:
        apps = self.start_apps()
        wanted = _norm(name)
        by_name = {_norm(a["name"]): a for a in apps}
        if wanted in by_name:
            return by_name[wanted]
        for alias in APP_ALIASES.get(wanted, []):
            if alias in by_name:
                return by_name[alias]
        starts = [a for n, a in by_name.items() if n.startswith(wanted)]
        if starts:
            return min(starts, key=lambda a: len(a["name"]))
        contains = [a for n, a in by_name.items() if wanted in n]
        if contains:
            return min(contains, key=lambda a: len(a["name"]))
        close = difflib.get_close_matches(wanted, list(by_name), n=1, cutoff=0.6)
        return by_name[close[0]] if close else None

    def open_app(self, name: str) -> str:
        app = self.find_app(name)
        if not app:
            raise LookupError(f"No encontré una aplicación instalada llamada {name!r}.")
        system.launch_app(app)
        return f"Abrí {app['name']}."

    def list_apps(self, filter: str = "") -> str:
        names = sorted({a["name"] for a in self.start_apps()}, key=str.lower)
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
        system.open_path(str(p))
        return f"Abrí {p.name or p}."

    def show_in_folder(self, path: str) -> str:
        p = self.files.resolve(path)
        if not p.exists():
            raise FileNotFoundError(f"No existe {p}.")
        system.reveal(str(p))
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
            if not system.press_media_key(key):
                return "No hay ningún reproductor que controlar ahora."
        return "Listo."


def register(reg: ToolRegistry, actions: Actions) -> None:
    reg.add("abrir_web", "Abre una página web en el navegador predeterminado. Para buscar algo en internet usa "
            "buscar_web; usa esta cuando el usuario quiera VER la página.", "Abriendo la página…",
            actions.open_web, {"url": {"type": "string", "description": "Dirección, p. ej. https://github.com"}},
            ["url"])
    if system.has("apps"):
        reg.add("abrir_app", "Abre una aplicación instalada por su nombre (Excel, Spotify, Calculadora, Configuración, "
                "Visual Studio Code…).", "Abriendo la aplicación…", actions.open_app, {"name": {"type": "string"}},
                ["name"])
        reg.add("listar_apps", "Lista las aplicaciones instaladas, opcionalmente filtradas por texto.",
                "Revisando tus aplicaciones…", actions.list_apps, {"filter": {"type": "string"}})
    reg.add("abrir_archivo", "Abre un archivo o carpeta con su programa predeterminado (documentos, imágenes, "
            "PDF, carpetas). Acepta alias como 'Descargas'. No abre programas ni scripts.", "Abriendo…",
            actions.open_path, {"path": {"type": "string"}}, ["path"])
    reg.add("mostrar_en_carpeta", "Abre el Explorador de archivos con el archivo seleccionado.",
            "Abriendo el Explorador…", actions.show_in_folder, {"path": {"type": "string"}}, ["path"])
    reg.add("multimedia", "Pausa, reanuda, pasa a la siguiente o vuelve a la anterior en la música o el video que "
            "esté sonando (Spotify primero). Para el volumen usa la herramienta volumen.",
            "Ajustando la música…", actions.media,
            {"action": {"type": "string", "enum": ["pausa", "reproducir", "siguiente", "anterior", "detener"]},
             "times": {"type": "integer", "description": "Repeticiones (p. ej. saltar 3 canciones, por defecto 1)"}},
            ["action"])
