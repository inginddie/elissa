"""Changing files, always behind an approval card: create or overwrite, edit (find and replace), move or rename,
and create folders. Everything stays inside the allowed folders; nothing is ever deleted.

The card shows exactly what will change (a diff). If the file changes between the preview and the user's click,
the action is refused instead of applying something the user didn't see.
"""
import difflib
import hashlib
import shutil
from pathlib import Path

from . import ToolRegistry
from .files import FileTools

MAX_WRITE = 300_000      # characters
MAX_DIFF_LINES = 400
BINARY_EXT = {".exe", ".dll", ".sys", ".msi", ".com", ".scr", ".lnk", ".docx", ".xlsx", ".pptx", ".pdf", ".zip",
              ".png", ".jpg", ".jpeg", ".gif", ".mp3", ".mp4", ".db", ".sqlite"}


def _digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "absent"


def _read(p: Path) -> str:
    raw = p.read_bytes()
    for enc in ("utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _diff(path: Path, old: str, new: str) -> str:
    lines = list(difflib.unified_diff(old.splitlines(), new.splitlines(), "antes", "después", n=2, lineterm=""))[2:]
    if len(lines) > MAX_DIFF_LINES:
        lines = lines[:MAX_DIFF_LINES] + [f"…({len(lines) - MAX_DIFF_LINES} líneas más)"]
    return "\n".join(lines) or "(sin cambios)"


class FileEditor:
    def __init__(self, files: FileTools):
        self.files = files
        self._seen: dict[str, str] = {}  # path -> digest the user saw in the preview

    def _target(self, path: str) -> Path:
        p = self.files.resolve(path)
        if p.suffix.lower() in BINARY_EXT:
            raise PermissionError(f"No edito archivos {p.suffix}: solo archivos de texto.")
        return p

    def _remember(self, p: Path) -> None:
        self._seen[str(p)] = _digest(p)

    def _check_unchanged(self, p: Path) -> None:
        if self._seen.pop(str(p), None) != _digest(p):
            raise RuntimeError("El archivo cambió desde que te mostré la vista previa; no apliqué nada.")

    # ----- write -----

    def write_preview(self, path: str, content: str) -> dict:
        p = self._target(path)
        if len(content) > MAX_WRITE:
            raise ValueError("El contenido es demasiado largo.")
        if p.exists() and p.is_dir():
            raise IsADirectoryError(f"{p} es una carpeta.")
        self._remember(p)
        if p.exists():
            return {"title": "Reemplazar el contenido de un archivo", "kind": "diff", "path": str(p),
                    "diff": _diff(p, _read(p), content), "warning": "Se reemplaza el archivo completo."}
        return {"title": "Crear un archivo", "kind": "diff", "path": str(p),
                "diff": "\n".join("+" + line for line in content.splitlines()[:MAX_DIFF_LINES])}

    def write(self, path: str, content: str) -> str:
        p = self._target(path)
        self._check_unchanged(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, "utf-8")
        return f"Guardé {p}."

    # ----- edit -----

    def _apply(self, p: Path, find: str, replace: str, replace_all: bool) -> str:
        if not p.is_file():
            raise FileNotFoundError(f"No existe el archivo {p}.")
        text = _read(p)
        count = text.count(find)
        if not find or count == 0:
            raise LookupError("No encontré ese texto en el archivo; léelo de nuevo y copia el fragmento exacto.")
        if count > 1 and not replace_all:
            raise LookupError(f"Ese texto aparece {count} veces; da más contexto o usa replace_all.")
        return text.replace(find, replace) if replace_all else text.replace(find, replace, 1)

    def edit_preview(self, path: str, find: str, replace: str, replace_all: bool = False) -> dict:
        p = self._target(path)
        new = self._apply(p, find, replace, replace_all)
        self._remember(p)
        return {"title": "Editar un archivo", "kind": "diff", "path": str(p), "diff": _diff(p, _read(p), new)}

    def edit(self, path: str, find: str, replace: str, replace_all: bool = False) -> str:
        p = self._target(path)
        self._check_unchanged(p)
        p.write_text(self._apply(p, find, replace, replace_all), "utf-8")
        return f"Edité {p}."

    # ----- move / rename / folders -----

    def _move_paths(self, source: str, destination: str) -> tuple[Path, Path]:
        src = self.files.resolve(source)
        dst = self.files.resolve(destination)
        if not src.exists():
            raise FileNotFoundError(f"No existe {src}.")
        if dst.is_dir():
            dst = dst / src.name
            self.files.resolve(str(dst))  # still inside the allowed folders
        if dst.exists():
            raise FileExistsError(f"Ya existe {dst}; no sobrescribo al mover.")
        return src, dst

    def move_preview(self, source: str, destination: str) -> dict:
        src, dst = self._move_paths(source, destination)
        what = "Renombrar" if src.parent == dst.parent else "Mover"
        return {"title": f"{what} {'carpeta' if src.is_dir() else 'archivo'}", "kind": "action",
                "lines": [f"De: {src}", f"A: {dst}"]}

    def move(self, source: str, destination: str) -> str:
        src, dst = self._move_paths(source, destination)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return f"Listo: ahora está en {dst}."

    def mkdir_preview(self, path: str) -> dict:
        p = self.files.resolve(path)
        if p.exists():
            raise FileExistsError(f"{p} ya existe.")
        return {"title": "Crear una carpeta", "kind": "action", "lines": [str(p)]}

    def mkdir(self, path: str) -> str:
        p = self.files.resolve(path)
        p.mkdir(parents=True, exist_ok=False)
        return f"Creé la carpeta {p}."


def register(reg: ToolRegistry, editor: FileEditor) -> None:
    reg.add("escribir_archivo", "Crea un archivo de texto o reemplaza todo su contenido (txt, md, csv, json, código…). "
            "El usuario verá el contenido o las diferencias y debe aprobarlo. Para cambios puntuales usa "
            "editar_archivo.", "Preparando el archivo…", editor.write,
            {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"],
            preview=editor.write_preview)
    reg.add("editar_archivo", "Cambia un fragmento exacto de un archivo de texto por otro (primero léelo para copiar "
            "el fragmento tal cual). El usuario ve las diferencias y debe aprobarlo.", "Preparando el cambio…",
            editor.edit,
            {"path": {"type": "string"}, "find": {"type": "string", "description": "Texto exacto a reemplazar"},
             "replace": {"type": "string"}, "replace_all": {"type": "boolean"}}, ["path", "find", "replace"],
            preview=editor.edit_preview)
    reg.add("mover_archivo", "Mueve o renombra un archivo o carpeta dentro de las carpetas permitidas. No sobrescribe.",
            "Preparando el movimiento…", editor.move,
            {"source": {"type": "string"}, "destination": {"type": "string",
                                                           "description": "Nueva ruta, o carpeta de destino"}},
            ["source", "destination"], preview=editor.move_preview)
    reg.add("crear_carpeta", "Crea una carpeta nueva.", "Preparando la carpeta…", editor.mkdir,
            {"path": {"type": "string"}}, ["path"], preview=editor.mkdir_preview)
