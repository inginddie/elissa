"""Timers, reminders and a simple task list, stored as files in Elissa's data folder.

Reminders survive restarts (recordatorios.json); one that came due while Elissa was closed fires on the next start.
Tasks are a Markdown checklist (tareas.md) the user can also edit by hand.
"""
import json
import re
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from . import ToolRegistry

TASK_RE = re.compile(r"^- \[( |x)\] (.+)$")


class Planner:
    def __init__(self, home: Path):
        self.reminders_file = home / "recordatorios.json"
        self.tasks_file = home / "tareas.md"
        self._lock = threading.Lock()

    # ----- reminders -----

    def _load(self) -> list[dict]:
        try:
            return json.loads(self.reminders_file.read_text("utf-8"))
        except (OSError, ValueError):
            return []

    def _save(self, items: list[dict]) -> None:
        self.reminders_file.parent.mkdir(parents=True, exist_ok=True)
        self.reminders_file.write_text(json.dumps(items, ensure_ascii=False, indent=1), "utf-8")

    def _add(self, when: datetime, text: str, kind: str) -> dict:
        item = {"id": uuid.uuid4().hex[:6], "when": when.isoformat(timespec="seconds"), "text": text.strip(),
                "kind": kind}
        with self._lock:
            items = self._load()
            items.append(item)
            self._save(sorted(items, key=lambda i: i["when"]))
        return item

    def timer(self, minutes: float, label: str = "") -> str:
        minutes = float(minutes)
        if not 0 < minutes <= 24 * 60:
            raise ValueError("El temporizador debe durar entre unos segundos y 24 horas.")
        when = datetime.now() + timedelta(minutes=minutes)
        self._add(when, label or "Se acabó el tiempo", "timer")
        return f"Temporizador listo: suena a las {when:%H:%M:%S}."

    def remind(self, text: str, in_minutes: float | None = None, at: str = "") -> str:
        if in_minutes:
            when = datetime.now() + timedelta(minutes=float(in_minutes))
        elif at:
            when = parse_when(at)
        else:
            raise ValueError("Dime cuándo: en cuántos minutos o a qué fecha y hora.")
        if when <= datetime.now():
            raise ValueError(f"Esa hora ya pasó ({when:%d/%m %H:%M}).")
        item = self._add(when, text, "reminder")
        return f"Recordatorio {item['id']} para el {when:%d/%m a las %H:%M}: {text}"

    def list_reminders(self) -> str:
        items = self._load()
        if not items:
            return "No hay recordatorios ni temporizadores pendientes."
        return "\n".join(f"{i['id']}: {datetime.fromisoformat(i['when']):%d/%m %H:%M} · "
                         f"{'temporizador' if i['kind'] == 'timer' else 'recordatorio'} · {i['text']}" for i in items)

    def cancel_reminder(self, id: str) -> str:
        with self._lock:
            items = self._load()
            keep = [i for i in items if i["id"] != id.strip()]
            if len(keep) == len(items):
                raise LookupError(f"No encontré el recordatorio {id}.")
            self._save(keep)
        return "Cancelado."

    def pop_due(self) -> list[dict]:
        """Reminders whose time has come (removed from the file). Called by the engine every few seconds."""
        now = datetime.now()
        with self._lock:
            items = self._load()
            due = [i for i in items if datetime.fromisoformat(i["when"]) <= now]
            if due:
                self._save([i for i in items if i not in due])
        for i in due:
            i["late"] = (now - datetime.fromisoformat(i["when"])).total_seconds() > 120
        return due

    # ----- tasks -----

    def _tasks(self) -> list[tuple[bool, str]]:
        if not self.tasks_file.exists():
            return []
        out = []
        for line in self.tasks_file.read_text("utf-8").splitlines():
            m = TASK_RE.match(line.strip())
            if m:
                out.append((m.group(1) == "x", m.group(2)))
        return out

    def _write_tasks(self, tasks: list[tuple[bool, str]]) -> None:
        self.tasks_file.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(f"- [{'x' if done else ' '}] {text}" for done, text in tasks)
        self.tasks_file.write_text(f"# Tareas\n\n{body}\n", "utf-8")

    def add_task(self, text: str, due: str = "") -> str:
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            raise ValueError("La tarea está vacía.")
        if due:
            text += f" (para {due.strip()})"
        with self._lock:
            tasks = self._tasks()
            tasks.append((False, text))
            self._write_tasks(tasks)
        return f"Anotada: {text}"

    def list_tasks(self, include_done: bool = False) -> str:
        tasks = self._tasks()
        shown = [(n, d, t) for n, (d, t) in enumerate(tasks, 1) if include_done or not d]
        if not shown:
            return "No tienes tareas pendientes." if not include_done else "No hay tareas."
        return "\n".join(f"{n}. {'(hecha) ' if d else ''}{t}" for n, d, t in shown)

    def complete_task(self, task: str) -> str:
        with self._lock:
            tasks = self._tasks()
            idx = int(task) - 1 if task.strip().isdigit() else next(
                (i for i, (d, t) in enumerate(tasks) if not d and task.lower() in t.lower()), -1)
            if not 0 <= idx < len(tasks):
                raise LookupError(f"No encontré la tarea {task!r}.")
            tasks[idx] = (True, tasks[idx][1])
            self._write_tasks(tasks)
        return f"Hecha: {tasks[idx][1]}"


def parse_when(text: str) -> datetime:
    """ISO date-time ('2026-10-12T09:30', '2026-10-12 09:30') or a time today/tomorrow ('15:30')."""
    text = text.strip().replace(" ", "T", 1) if re.match(r"^\d{4}-\d{2}-\d{2} ", text.strip()) else text.strip()
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    m = re.fullmatch(r"(\d{1,2})[:.h](\d{2})", text)
    if m:
        now = datetime.now()
        when = now.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
        return when if when > now else when + timedelta(days=1)
    raise ValueError(f"No entendí la hora {text!r}; usa el formato 2026-10-12T15:30 o 15:30.")


def register(reg: ToolRegistry, planner: Planner) -> None:
    reg.add("temporizador", "Pone un temporizador: Elissa avisa con sonido, voz y notificación cuando se cumple.",
            "Poniendo el temporizador…", planner.timer,
            {"minutes": {"type": "number", "description": "Duración en minutos (admite decimales)"},
             "label": {"type": "string", "description": "Para qué es (opcional)"}}, ["minutes"])
    reg.add("crear_recordatorio", "Crea un recordatorio para dentro de X minutos o para una fecha y hora. Usa la "
            "fecha y hora actuales del mensaje del usuario para calcular.", "Creando el recordatorio…",
            planner.remind,
            {"text": {"type": "string", "description": "Qué recordar, redactado para leerlo en voz alta"},
             "in_minutes": {"type": "number"},
             "at": {"type": "string", "description": "Fecha y hora local ISO, p. ej. 2026-10-12T09:30, o HH:MM"}},
            ["text"])
    reg.add("listar_recordatorios", "Lista recordatorios y temporizadores pendientes con su id.",
            "Revisando tus recordatorios…", planner.list_reminders)
    reg.add("cancelar_recordatorio", "Cancela un recordatorio o temporizador por su id.", "Cancelando…",
            planner.cancel_reminder, {"id": {"type": "string"}}, ["id"])
    reg.add("agregar_tarea", "Anota una tarea en la lista de pendientes del usuario.", "Anotando la tarea…",
            planner.add_task, {"text": {"type": "string"},
                               "due": {"type": "string", "description": "Para cuándo (opcional, texto libre)"}},
            ["text"])
    reg.add("listar_tareas", "Lista las tareas pendientes (o todas).", "Revisando tus tareas…", planner.list_tasks,
            {"include_done": {"type": "boolean"}})
    reg.add("completar_tarea", "Marca una tarea como hecha, por su número en la lista o por parte de su texto.",
            "Marcando la tarea…", planner.complete_task, {"task": {"type": "string"}}, ["task"])
