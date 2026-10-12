"""Coding assistant tools: look at a project, search code, read numbered lines, inspect git, and run commands.

Reading is free. Running a command needs approval (the card shows the exact command and folder), and commands that
delete or throw work away are refused outright, so Elissa keeps her promise of never deleting anything.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

from . import ToolRegistry
from .files import SKIP_DIRS, FileTools

MAX_OUTPUT = 12000
MAX_TREE_ENTRIES = 400
CODE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".json", ".toml", ".yaml", ".yml", ".md", ".txt",
            ".rs", ".go", ".java", ".kt", ".cs", ".cpp", ".c", ".h", ".hpp", ".rb", ".php", ".swift", ".sql", ".sh",
            ".ps1", ".bat", ".cmd", ".html", ".css", ".scss", ".vue", ".svelte", ".xml", ".ini", ".cfg", ".env.example",
            ".gradle", ".properties", ".dockerfile", ".tf", ".lua", ".dart", ".r", ".scala", ".csv"}
MARKERS = {"pyproject.toml": "Python", "requirements.txt": "Python", "package.json": "Node/JavaScript",
           "Cargo.toml": "Rust", "go.mod": "Go", "pom.xml": "Java (Maven)", "build.gradle": "Java/Kotlin (Gradle)",
           "build.gradle.kts": "Kotlin (Gradle)", "*.csproj": ".NET", "*.sln": ".NET", "Gemfile": "Ruby",
           "composer.json": "PHP", "Dockerfile": "Docker", ".git": "repositorio git"}

# Commands Elissa never runs: they delete files or throw work away. The user can still run them themselves.
FORBIDDEN = [
    (r"\b(remove-item|rm|rmdir|rd|del|erase|ri)\b", "borra archivos o carpetas"),
    (r"\bgit\s+(clean|reset\s+--hard|checkout\s+--\s|restore\b|stash\s+(drop|clear))", "descarta cambios de git"),
    (r"\bgit\s+push\b.*(--force|-f\b|--mirror|--delete|\s:)", "reescribe o borra ramas remotas"),
    (r"\bgit\s+branch\s+(-d|--delete)\b", "borra una rama"),
    (r"\b(format|diskpart|bcdedit|vssadmin|cipher\s+/w|shutdown|restart-computer|stop-computer)\b",
     "toca el sistema o los discos"),
    (r"\breg(\.exe)?\s+delete\b|remove-itemproperty", "borra del registro de Windows"),
    (r"\b(drop\s+(table|database)|truncate\s+table)\b", "borra datos de una base de datos"),
    (r"\b(iex|invoke-expression)\b|\|\s*(sh|bash|iex|powershell)\b", "ejecuta código descargado o dinámico"),
]
# Commands that run but deserve a warning on the card.
RISKY = [
    (r"\bgit\s+(push|commit|merge|rebase|tag)\b", "Cambia el repositorio (o lo publica)."),
    (r"\b(npm|pnpm|yarn)\s+publish\b|\btwine\s+upload\b|\bcargo\s+publish\b", "Publica un paquete."),
    (r"\b(stop-process|taskkill|kill)\b", "Detiene procesos."),
    (r"\b(move-item|mv|move|rename-item|ren)\b", "Mueve o renombra archivos."),
    (r"\b(set-content|out-file|add-content)\b|>\s*\S", "Escribe en archivos."),
    (r"\b(pip|uv|npm|pnpm|yarn|winget|choco|cargo)\s+(install|add|i|update|upgrade|remove|uninstall)\b",
     "Instala o cambia dependencias."),
    (r"\b(curl|wget|invoke-webrequest|iwr)\b", "Descarga de internet."),
]


def forbidden_reason(command: str) -> str | None:
    lowered = command.lower()
    return next((why for pattern, why in FORBIDDEN if re.search(pattern, lowered)), None)


def risk_warning(command: str) -> str:
    lowered = command.lower()
    return " ".join(why for pattern, why in RISKY if re.search(pattern, lowered))


def _clip(text: str) -> str:
    if len(text) <= MAX_OUTPUT:
        return text
    half = MAX_OUTPUT // 2
    return f"{text[:half]}\n…({len(text) - MAX_OUTPUT} caracteres omitidos)…\n{text[-half:]}"


class CodeTools:
    def __init__(self, files: FileTools):
        self.files = files

    def _dir(self, path: str) -> Path:
        p = self.files.resolve(path)
        if not p.is_dir():
            raise NotADirectoryError(f"{p} no es una carpeta.")
        return p

    # ----- reading -----

    def project(self, path: str, depth: int = 3) -> str:
        root = self._dir(path)
        kinds = sorted({kind for marker, kind in MARKERS.items()
                        if (list(root.glob(marker)) if "*" in marker else (root / marker).exists())})
        lines, count = [], 0
        depth = max(1, min(int(depth or 3), 6))

        def walk(folder: Path, level: int, prefix: str) -> None:
            nonlocal count
            try:
                entries = sorted(folder.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
            except OSError:
                return
            for e in entries:
                if e.name in SKIP_DIRS or (e.name.startswith(".") and e.name not in (".github", ".env.example")):
                    continue
                count += 1
                if count > MAX_TREE_ENTRIES:
                    return
                lines.append(f"{prefix}{e.name}{'/' if e.is_dir() else ''}")
                if e.is_dir() and level < depth:
                    walk(e, level + 1, prefix + "  ")

        walk(root, 1, "")
        more = "\n…(hay más; usa una carpeta más específica)" if count > MAX_TREE_ENTRIES else ""
        head = f"Proyecto {root}" + (f" · {', '.join(kinds)}" if kinds else "")
        return f"{head}\n" + "\n".join(lines) + more

    def search(self, pattern: str, path: str, glob: str = "", regex: bool = False, limit: int = 60) -> str:
        root = self.files.resolve(path)
        limit = max(1, min(int(limit or 60), 200))
        rg = shutil.which("rg")
        if rg:
            args = [rg, "-n", "--no-heading", "-S", "--max-columns", "240", "-m", "8"]
            if not regex:
                args.append("-F")
            for skip in SKIP_DIRS:
                args += ["-g", f"!{skip}"]
            if glob:
                args += ["-g", glob]
            args += ["--", pattern, str(root)]
            out = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                 timeout=30, creationflags=subprocess.CREATE_NO_WINDOW).stdout.splitlines()
        else:
            out = self._search_python(root, pattern, glob, regex, limit)
        out = out[:limit]
        return "\n".join(out) or f"No encontré {pattern!r} en {root}."

    def _search_python(self, root: Path, pattern: str, glob: str, regex: bool, limit: int) -> list[str]:
        import fnmatch
        rx = re.compile(pattern if regex else re.escape(pattern), re.I)
        out = []
        files = [root] if root.is_file() else (
            Path(d) / f for d, dirs, fs in os.walk(root)
            if not dirs.__setitem__(slice(None), [x for x in dirs if x not in SKIP_DIRS and not x.startswith(".")])
            for f in fs)
        for f in files:
            if glob and not fnmatch.fnmatch(f.name, glob):
                continue
            if f.suffix.lower() not in CODE_EXT or f.stat().st_size > 1_000_000:
                continue
            try:
                for n, line in enumerate(f.read_text("utf-8", errors="replace").splitlines(), 1):
                    if rx.search(line):
                        out.append(f"{f}:{n}:{line.strip()[:240]}")
                        if len(out) >= limit:
                            return out
            except OSError:
                continue
        return out

    def read_lines(self, path: str, start: int = 1, end: int = 0) -> str:
        p = self.files.resolve(path)
        if not p.is_file():
            raise FileNotFoundError(f"No existe el archivo {p}.")
        lines = p.read_text("utf-8", errors="replace").splitlines()
        start = max(1, int(start or 1))
        end = min(len(lines), int(end) if end else start + 299)
        body = "\n".join(f"{n:>5}  {lines[n - 1]}" for n in range(start, end + 1))
        more = f"\n…(el archivo tiene {len(lines)} líneas)" if end < len(lines) else ""
        return f"[{p.name} · líneas {start}-{end}]\n{body}{more}"

    def git(self, path: str, action: str = "status") -> str:
        root = self._dir(path)
        git = shutil.which("git")
        if not git:
            raise RuntimeError("Git no está instalado en este PC.")
        commands = {
            "status": [["status", "--short", "--branch"]],
            "diff": [["diff", "--stat"], ["diff"]],
            "staged": [["diff", "--cached", "--stat"], ["diff", "--cached"]],
            "log": [["log", "--oneline", "--decorate", "-n", "20"]],
            "branches": [["branch", "-vv"]],
        }
        if action not in commands:
            raise ValueError(f"Acción desconocida. Opciones: {', '.join(commands)}.")
        parts = []
        for args in commands[action]:
            r = subprocess.run([git, "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
            parts.append((r.stdout or r.stderr).strip())
        return _clip("\n\n".join(p for p in parts if p) or "(sin cambios)")

    # ----- running commands -----

    def run_preview(self, command: str, path: str, timeout: int = 120) -> dict:
        cwd = self._dir(path)
        why = forbidden_reason(command)
        if why:
            raise PermissionError(f"No ejecuto ese comando porque {why}. Si de verdad hace falta, el usuario puede "
                                  "correrlo él mismo.")
        return {"title": "Ejecutar un comando", "kind": "command", "cwd": str(cwd), "command": command.strip(),
                "warning": risk_warning(command), "subtitle": f"Tiempo máximo: {int(timeout)} s"}

    def run(self, command: str, path: str, timeout: int = 120) -> str:
        cwd = self._dir(path)
        if forbidden_reason(command):
            raise PermissionError("Comando no permitido.")
        timeout = max(5, min(int(timeout or 120), 1800))
        proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + command],
            cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            raw, _ = proc.communicate(timeout=timeout)
            status = f"Terminó con código {proc.returncode}."
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            raw, _ = proc.communicate()
            status = f"Lo detuve: pasó de {timeout} s."
        out = raw.decode("utf-8", errors="replace").strip()
        return f"{status}\n{_clip(out) if out else '(sin salida)'}"


def register(reg: ToolRegistry, code: CodeTools) -> None:
    reg.add("ver_proyecto", "Muestra la estructura de un proyecto de software (árbol de carpetas sin node_modules, "
            ".venv, etc.) y su tipo (Python, Node, Rust…). Empieza por aquí para entender un proyecto.",
            "Mirando el proyecto…", code.project,
            {"path": {"type": "string"}, "depth": {"type": "integer", "description": "Profundidad (1-6, por defecto 3)"}},
            ["path"])
    reg.add("buscar_codigo", "Busca texto o una expresión regular en el código de un proyecto y devuelve "
            "archivo:línea:contenido.", "Buscando en el código…", code.search,
            {"pattern": {"type": "string"}, "path": {"type": "string"},
             "glob": {"type": "string", "description": "Filtro de archivos, p. ej. *.py"},
             "regex": {"type": "boolean"}, "limit": {"type": "integer"}}, ["pattern", "path"])
    reg.add("leer_lineas", "Lee un rango de líneas de un archivo de código con números de línea (por defecto 300 "
            "líneas desde 'start'). Úsalo antes de editar para copiar el fragmento exacto.", "Leyendo el código…",
            code.read_lines, {"path": {"type": "string"}, "start": {"type": "integer"}, "end": {"type": "integer"}},
            ["path"])
    reg.add("git", "Consulta git en un proyecto (solo lectura): status, diff, staged, log, branches.",
            "Revisando git…", code.git,
            {"path": {"type": "string"}, "action": {"type": "string",
                                                    "enum": ["status", "diff", "staged", "log", "branches"]}},
            ["path"])
    reg.add("ejecutar_comando", "Ejecuta un comando de PowerShell en la carpeta de un proyecto (tests, build, lint, "
            "git commit…) y devuelve la salida. El usuario ve el comando exacto y debe aprobarlo. Nunca borra "
            "archivos ni descarta trabajo.", "Preparando el comando…", code.run,
            {"command": {"type": "string"}, "path": {"type": "string", "description": "Carpeta donde se ejecuta"},
             "timeout": {"type": "integer", "description": "Segundos (por defecto 120)"}},
            ["command", "path"], preview=code.run_preview)
