"""Tool registry: tools are plain Python functions plus a JSON schema; the agent stays provider-neutral."""
import asyncio
import inspect
import logging
from dataclasses import dataclass
from typing import Callable

from ..llm import ToolCall, ToolResult, ToolSpec

log = logging.getLogger(__name__)

MAX_RESULT_CHARS = 20000


@dataclass
class Tool:
    spec: ToolSpec
    fn: Callable
    label: str  # what the UI shows while it runs, e.g. "Revisando tu correo…"


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def add(self, name: str, description: str, label: str, fn: Callable,
            properties: dict | None = None, required: list[str] | None = None) -> None:
        schema = {"type": "object", "properties": properties or {}, "required": required or []}
        self._tools[name] = Tool(ToolSpec(name, description, schema), fn, label)

    def clear(self) -> None:
        self._tools.clear()

    def specs(self) -> list[ToolSpec]:
        return [t.spec for t in self._tools.values()]

    def label(self, name: str) -> str:
        tool = self._tools.get(name)
        return tool.label if tool else f"Usando {name}…"

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
            if inspect.iscoroutinefunction(tool.fn):
                out = await tool.fn(**args)
            else:
                out = await asyncio.to_thread(tool.fn, **args)
        except Exception as e:  # tool failures go back to the model, they don't crash the turn
            log.warning("tool %s failed: %s", call.name, e)
            return ToolResult(call.id, call.name, f"Error: {e}", True)
        text = str(out)
        if len(text) > MAX_RESULT_CHARS:
            text = text[:MAX_RESULT_CHARS] + "\n…(resultado recortado)"
        return ToolResult(call.id, call.name, text)
