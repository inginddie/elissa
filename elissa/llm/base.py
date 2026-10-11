"""Provider-neutral conversation types and the interface every LLM adapter implements."""
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class ToolResult:
    call_id: str
    name: str
    content: str
    is_error: bool = False


@dataclass
class Message:
    """One entry of the neutral history.

    role "user" carries `text`; role "assistant" carries `text` and/or `tool_calls`;
    role "tool" carries `results` (answers to the previous assistant's tool calls).
    `raw` keeps the provider-native assistant content (e.g. Anthropic thinking blocks, which must be
    replayed unchanged); it is only reused when talking to that same provider.
    """
    role: str
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    results: list[ToolResult] = field(default_factory=list)
    raw: tuple[str, object] | None = None  # (provider_id, native content)


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON Schema object


OnText = Callable[[str], Awaitable[None]]


class LLMError(Exception):
    """Readable error for the UI (bad key, model not found, provider down...)."""


class Provider(Protocol):
    id: str

    async def stream(self, system: str, history: list[Message], tools: list[ToolSpec],
                     on_text: OnText) -> Message:
        """Stream one assistant turn, calling on_text for each text fragment; return the full message."""

    async def complete(self, system: str, prompt: str) -> str:
        """Single non-streaming, tool-less completion (summaries, memory)."""

    async def list_models(self) -> list[str]:
        """Model ids available to this key/endpoint (used by the setup wizard)."""
