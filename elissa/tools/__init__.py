"""Tool registry: tools are plain Python functions plus a JSON schema; the agent stays provider-neutral.

Tools that change something (send, write, click…) also have a `preview` function. Before such a tool runs, the
registry builds its preview and asks the user through the approver (an approval card in the UI). The model never
gets to approve: the decision only comes from a click in Elissa's window.
"""
import asyncio
import inspect
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

from ..llm import ToolCall, ToolResult, ToolSpec

log = logging.getLogger(__name__)

MAX_RESULT_CHARS = 20000
DENIED = ("El usuario NO aprobó esta acción y no se ejecutó. No la repitas ni insistas; pregúntale qué prefiere "
          "si hace falta.")

# preview(**args) -> {"title": str, "kind": "text"|"diff"|"email"|"action", ...details for the card}
Preview = Callable[..., dict]
Approver = Callable[[str, dict], Awaitable[bool]]


@dataclass
class Tool:
    spec: ToolSpec
    fn: Callable
    label: str  # what the UI shows while it runs, e.g. "Revisando tu correo…"
    preview: Preview | None = None


async def _call(fn: Callable, args: dict):
    if inspect.iscoroutinefunction(fn):
        return await fn(**args)
    return await asyncio.to_thread(fn, **args)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self.approver: Approver | None = None
        self._approval_lock = asyncio.Lock()  # one approval card at a time

    def add(self, name: str, description: str, label: str, fn: Callable,
            properties: dict | None = None, required: list[str] | None = None,
            preview: Preview | None = None) -> None:
        schema = {"type": "object", "properties": properties or {}, "required": required or []}
        self._tools[name] = Tool(ToolSpec(name, description, schema), fn, label, preview)

    def clear(self) -> None:
        self._tools.clear()

    def specs(self) -> list[ToolSpec]:
        return [t.spec for t in self._tools.values()]

    def label(self, name: str) -> str:
        tool = self._tools.get(name)
        return tool.label if tool else f"Usando {name}…"

    def needs_approval(self, name: str) -> bool:
        tool = self._tools.get(name)
        return bool(tool and tool.preview)

    async def run(self, call: ToolCall) -> ToolResult:
        tool = self._tools.get(call.name)
        if not tool:
            return ToolResult(call.id, call.name, f"La herramienta {call.name!r} no existe.", True)
        if "_invalid_json" in call.args:
            return ToolResult(call.id, call.name, "Los argumentos no eran JSON válido; inténtalo de nuevo.", True)
        props = tool.spec.parameters["properties"]
        missing = [k for k in tool.spec.parameters["required"] if k not in call.args]
        if missing:
            return ToolResult(call.id, call.name, f"Faltan argumentos: {', '.join(missing)}.", True)
        args = {k: v for k, v in call.args.items() if k in props}
        try:
            if tool.preview:
                # The preview also validates (paths, addresses…): a bad request fails before bothering the user.
                card = await _call(tool.preview, args)
                async with self._approval_lock:
                    approved = bool(self.approver) and await self.approver(call.name, card)
                if not approved:
                    log.info("tool %s denied by the user", call.name)
                    return ToolResult(call.id, call.name, DENIED)
                log.info("tool %s approved by the user", call.name)
            out = await _call(tool.fn, args)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # tool failures go back to the model, they don't crash the turn
            log.warning("tool %s failed: %s", call.name, e)
            return ToolResult(call.id, call.name, f"Error: {e}", True)
        text = str(out)
        if len(text) > MAX_RESULT_CHARS:
            text = text[:MAX_RESULT_CHARS] + "\n…(resultado recortado)"
        return ToolResult(call.id, call.name, text)
