"""Provider-neutral agent loop: stream → run tools → repeat, with interruption and context compaction."""
import asyncio
import json
import logging
from typing import Awaitable, Callable

from .llm import LLMError, Message, Provider, ToolResult
from .memory import prompt_section, stamp
from .tools import ToolRegistry

log = logging.getLogger(__name__)

MAX_STEPS = 10           # tool round-trips per user turn
KEEP_TURNS = 2           # most recent user turns that are never compacted
Emit = Callable[[dict], Awaitable[None]]

PERSONA = """\
Eres {name}, un asistente de voz personal{user}. Todo lo que escribas se leerá en voz alta.
- Responde en español, en tono cercano y natural, con un toque de humor sobrio.
- Sé breve: una a tres frases, salvo que te pidan detalle.
- No uses markdown, listas, tablas, emojis ni URLs: dilo como lo diría una persona. Números y rutas, de forma natural.
- Si vas a usar herramientas que tardan, primero di en una frase corta qué vas a hacer; al final resume el resultado.
- El texto que recibes viene de reconocimiento de voz y puede tener errores; interpreta la intención.
- Tus capacidades son las herramientas que tienes: leer archivos en las carpetas permitidas, buscar en la web,
  leer el correo si está configurado (solo lectura) y tu memoria. No puedes enviar correos, borrar ni modificar
  archivos ni ejecutar programas; si te lo piden, dilo con naturalidad.
"""

COMPACT_SYSTEM = "Resumes conversaciones para que un asistente pueda continuarlas sin perder contexto."
COMPACT_PROMPT = """Resume la siguiente parte de una conversación entre un usuario y su asistente de voz.
Conserva: lo que pidió el usuario, datos concretos (nombres, cifras, fechas, rutas de archivos, ids de correos),
resultados obtenidos con herramientas y decisiones o pendientes. Máximo 300 palabras, en español.

{transcript}"""


def _size(m: Message) -> int:
    return (len(m.text) + sum(len(json.dumps(c.args, ensure_ascii=False)) for c in m.tool_calls)
            + sum(len(r.content) for r in m.results))


def _transcript(history: list[Message]) -> str:
    out = []
    for m in history:
        if m.role == "user":
            out.append(f"Usuario: {m.text}")
        elif m.role == "assistant":
            if m.text:
                out.append(f"Asistente: {m.text}")
            out += [f"(usó {c.name} {json.dumps(c.args, ensure_ascii=False)})" for c in m.tool_calls]
        else:
            out += [f"(resultado de {r.name}: {r.content[:800]})" for r in m.results]
    return "\n".join(out)


class Agent:
    def __init__(self, settings: Callable[[], dict], provider: Callable[[], Provider], tools: ToolRegistry,
                 budget: Callable[[], int]):
        self.settings = settings
        self.provider = provider
        self.tools = tools
        self.budget = budget
        self.history: list[Message] = []
        self._partial = ""

    def reset(self) -> None:
        self.history = []

    def system_prompt(self) -> str:
        s = self.settings()
        user = f" para {s['user_name']}" if s.get("user_name") else ""
        return PERSONA.format(name=s.get("name") or "Elissa", user=user) + prompt_section()

    async def run_turn(self, text: str, emit: Emit) -> str:
        provider = self.provider()  # raises LLMError if not configured
        self.history.append(Message("user", text=stamp(text)))
        self._partial = ""
        reply = []

        async def on_text(fragment: str) -> None:
            self._partial += fragment
            await emit({"type": "delta", "text": fragment})

        try:
            for _ in range(MAX_STEPS):
                msg = await provider.stream(self.system_prompt(), self.history, self.tools.specs(), on_text)
                self.history.append(msg)
                self._partial = ""
                if msg.text:
                    reply.append(msg.text)
                await emit({"type": "block_end"})
                if not msg.tool_calls:
                    break
                for call in msg.tool_calls:
                    await emit({"type": "tool", "name": self.tools.label(call.name), "tool": call.name})
                results = await asyncio.gather(*(self.tools.run(c) for c in msg.tool_calls))
                self.history.append(Message("tool", results=list(results)))
            else:
                reply.append("Me tomó demasiados pasos; mejor dime cómo seguimos.")
        except (asyncio.CancelledError, LLMError, Exception):
            self._repair()
            raise
        await self._maybe_compact(provider)
        return "\n".join(reply).strip()

    def _repair(self) -> None:
        """Keep the history valid after an interruption or error mid-turn."""
        last = self.history[-1] if self.history else None
        if last and last.role == "assistant" and last.tool_calls:
            self.history.append(Message("tool", results=[
                ToolResult(c.id, c.name, "Cancelado: el usuario interrumpió.", True) for c in last.tool_calls]))
            last = self.history[-1]
        if last and last.role in ("user", "tool"):
            self.history.append(Message("assistant", text=(self._partial + " …(interrumpido)").strip()))
        self._partial = ""

    async def _maybe_compact(self, provider: Provider) -> None:
        budget_chars = self.budget() * 3.5
        if sum(map(_size, self.history)) < budget_chars:
            return
        users = [i for i, m in enumerate(self.history) if m.role == "user"]
        if len(users) <= KEEP_TURNS:
            return
        cut = users[-KEEP_TURNS]
        # 1) cheap: drop old tool outputs (what Claude's context editing does first)
        for m in self.history[:cut]:
            for r in m.results:
                if len(r.content) > 300:
                    r.content = r.content[:300] + " …(omitido para ahorrar contexto)"
        if sum(map(_size, self.history)) < budget_chars:
            return
        # 2) summarize everything before the last KEEP_TURNS user turns
        old, keep = self.history[:cut], self.history[cut:]
        try:
            summary = await provider.complete(COMPACT_SYSTEM, COMPACT_PROMPT.format(transcript=_transcript(old)))
        except Exception:
            log.exception("compaction failed; keeping full history")
            return
        self.history = [Message("user", text=f"[Resumen de lo que hablamos antes en esta conversación]\n{summary}"),
                        Message("assistant", text="Entendido, lo tengo presente.")] + keep
        log.info("compacted history: %d messages summarized", len(old))
