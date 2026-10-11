"""Any OpenAI-compatible chat completions API: OpenAI, OpenRouter, Gemini, Groq, Ollama, LM Studio..."""
import json

import openai

from .base import LLMError, Message, OnText, ToolCall, ToolSpec


def _errors(e: Exception, label: str) -> LLMError:
    if isinstance(e, openai.AuthenticationError):
        return LLMError(f"La API key de {label} no es válida.")
    if isinstance(e, openai.NotFoundError):
        return LLMError(f"{label} no reconoce ese modelo.")
    if isinstance(e, openai.RateLimitError):
        return LLMError(f"{label} está limitando las peticiones o no tienes saldo.")
    if isinstance(e, openai.APIConnectionError):
        return LLMError(f"No hay conexión con {label}. ¿Está encendido o hay internet?")
    if isinstance(e, openai.APIStatusError):
        return LLMError(f"{label} respondió con error {e.status_code}.")
    return LLMError(str(e))


class OpenAICompatProvider:
    def __init__(self, provider_id: str, label: str, base_url: str, api_key: str, model: str):
        self.id = provider_id
        self.label = label
        self.model = model
        self.client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key or "sin-clave", max_retries=2)

    def _messages(self, system: str, history: list[Message]) -> list[dict]:
        out: list[dict] = [{"role": "system", "content": system}]
        for m in history:
            if m.role == "user":
                out.append({"role": "user", "content": m.text})
            elif m.role == "assistant":
                msg: dict = {"role": "assistant", "content": m.text or None}
                if m.tool_calls:
                    msg["tool_calls"] = [{"id": c.id, "type": "function",
                                          "function": {"name": c.name, "arguments": json.dumps(c.args, ensure_ascii=False)}}
                                         for c in m.tool_calls]
                elif not m.text:
                    msg["content"] = "…"
                out.append(msg)
            elif m.role == "tool":
                out.extend({"role": "tool", "tool_call_id": r.call_id, "content": r.content} for r in m.results)
        return out

    async def stream(self, system: str, history: list[Message], tools: list[ToolSpec], on_text: OnText) -> Message:
        params: dict = {"model": self.model, "messages": self._messages(system, history), "stream": True}
        if tools:
            params["tools"] = [{"type": "function", "function": {
                "name": t.name, "description": t.description, "parameters": t.parameters}} for t in tools]
        text = []
        calls: dict[int, dict] = {}
        finish = None
        try:
            stream = await self.client.chat.completions.create(**params)
            async for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta
                if delta.content:
                    text.append(delta.content)
                    await on_text(delta.content)
                for tc in delta.tool_calls or []:
                    slot = calls.setdefault(tc.index or 0, {"id": "", "name": "", "args": ""})
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function and tc.function.name:
                        slot["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        slot["args"] += tc.function.arguments
                finish = choice.finish_reason or finish
        except openai.APIError as e:
            raise _errors(e, self.label) from e

        tool_calls = []
        if finish != "length":  # truncated tool arguments must not be executed
            for i, slot in sorted(calls.items()):
                try:
                    args = json.loads(slot["args"] or "{}")
                except json.JSONDecodeError:
                    args = {"_invalid_json": slot["args"]}
                tool_calls.append(ToolCall(slot["id"] or f"call_{i}", slot["name"], args if isinstance(args, dict) else {}))
        return Message("assistant", text="".join(text), tool_calls=tool_calls)

    async def complete(self, system: str, prompt: str) -> str:
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}])
        except openai.APIError as e:
            raise _errors(e, self.label) from e
        return resp.choices[0].message.content or ""

    async def list_models(self) -> list[str]:
        try:
            return sorted([m.id async for m in self.client.models.list()])
        except openai.APIError as e:
            raise _errors(e, self.label) from e
