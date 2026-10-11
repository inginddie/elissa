"""Claude via the official Anthropic SDK (Messages API, streaming, client-side tools)."""
import anthropic

from .base import LLMError, Message, OnText, ToolCall, ToolSpec

DEFAULT_MODEL = "claude-opus-5-5"
# Models that support server-side refusal fallbacks with the "default" routing.
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}


def _errors(e: Exception) -> LLMError:
    if isinstance(e, anthropic.AuthenticationError):
        return LLMError("La API key de Anthropic no es válida.")
    if isinstance(e, anthropic.PermissionDeniedError):
        return LLMError("Tu API key no tiene permiso para este modelo.")
    if isinstance(e, anthropic.NotFoundError):
        return LLMError("Ese modelo no existe en Anthropic.")
    if isinstance(e, anthropic.RateLimitError):
        return LLMError("Anthropic está limitando las peticiones; espera un momento.")
    if isinstance(e, anthropic.APIStatusError):
        return LLMError(f"Anthropic respondió con error {e.status_code}.")
    if isinstance(e, anthropic.APIConnectionError):
        return LLMError("No hay conexión con Anthropic.")
    return LLMError(str(e))


class AnthropicProvider:
    id = "anthropic"

    def __init__(self, api_key: str, model: str = ""):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model or DEFAULT_MODEL

    def _extra(self) -> dict:
        if self.model in FALLBACK_MODELS:
            # On a policy decline the API re-runs the request on a fallback model in the same call.
            return {"extra_headers": {"anthropic-beta": "server-side-fallback-2026-07-01"},
                    "extra_body": {"fallbacks": "default"}}
        return {}

    def _messages(self, history: list[Message]) -> list[dict]:
        out = []
        for m in history:
            if m.role == "user":
                out.append({"role": "user", "content": m.text})
            elif m.role == "assistant":
                if m.raw and m.raw[0] == self.id:
                    content = m.raw[1]  # replay unchanged (keeps thinking blocks valid)
                else:
                    content = ([{"type": "text", "text": m.text}] if m.text else []) + [
                        {"type": "tool_use", "id": c.id, "name": c.name, "input": c.args} for c in m.tool_calls]
                out.append({"role": "assistant", "content": content or [{"type": "text", "text": "…"}]})
            elif m.role == "tool":
                out.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": r.call_id, "content": r.content, "is_error": r.is_error}
                    for r in m.results]})
        return out

    async def stream(self, system: str, history: list[Message], tools: list[ToolSpec], on_text: OnText) -> Message:
        params = dict(
            model=self.model,
            max_tokens=16000,
            system=system,
            messages=self._messages(history),
            output_config={"effort": "medium"},
            **self._extra(),
        )
        if tools:
            params["tools"] = [{"name": t.name, "description": t.description, "input_schema": t.parameters}
                               for t in tools]
        try:
            async with self.client.messages.stream(**params) as stream:
                async for event in stream:
                    if event.type == "text":
                        await on_text(event.text)
                final = await stream.get_final_message()
        except anthropic.APIError as e:
            raise _errors(e) from e

        text = "".join(b.text for b in final.content if b.type == "text")
        calls = [ToolCall(b.id, b.name, b.input if isinstance(b.input, dict) else {})
                 for b in final.content if b.type == "tool_use"]
        if final.stop_reason == "refusal" and not text:
            text = "Prefiero no ayudar con eso."
        if final.stop_reason == "max_tokens":
            calls = []  # a truncated tool input must not be executed
        return Message("assistant", text=text, tool_calls=calls, raw=(self.id, final.content))

    async def complete(self, system: str, prompt: str) -> str:
        try:
            resp = await self.client.messages.create(
                model=self.model, max_tokens=8000, system=system,
                messages=[{"role": "user", "content": prompt}],
                output_config={"effort": "low"}, **self._extra())
        except anthropic.APIError as e:
            raise _errors(e) from e
        return "".join(b.text for b in resp.content if b.type == "text")

    async def list_models(self) -> list[str]:
        try:
            return [m.id async for m in self.client.models.list()]
        except anthropic.APIError as e:
            raise _errors(e) from e
