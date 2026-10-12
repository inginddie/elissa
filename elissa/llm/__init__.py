"""Provider catalogue and factory. Adding a provider = one entry in PROVIDERS."""
from ..config import api_key_name, get_secret
from .anthropic_provider import AnthropicProvider
from .base import LLMError, Message, Provider, ToolCall, ToolResult, ToolSpec
from .openai_provider import OpenAICompatProvider

# kind: "anthropic" uses the native SDK; "openai" any OpenAI-compatible endpoint.
# suggested: a starting point shown in the wizard; the wizard also lists the endpoint's real models.
PROVIDERS = {
    "openai": {"label": "OpenAI", "kind": "openai", "base_url": "https://api.openai.com/v1",
               "needs_key": True, "suggested": "gpt-6-luna", "key_url": "https://platform.openai.com/api-keys",
               "budget": 60000},
    "openrouter": {"label": "OpenRouter", "kind": "openai", "base_url": "https://openrouter.ai/api/v1",
                   "needs_key": True, "suggested": "openai/gpt-6-luna", "key_url": "https://openrouter.ai/keys",
                   "budget": 60000},
    "anthropic": {"label": "Anthropic (Claude)", "kind": "anthropic", "base_url": "",
                  "needs_key": True, "suggested": "claude-haiku-5-5",
                  "key_url": "https://console.anthropic.com/settings/keys", "budget": 60000},
    "gemini": {"label": "Google Gemini", "kind": "openai",
               "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
               "needs_key": True, "suggested": "gemini-3.5-flash-lite", "key_url": "https://aistudio.google.com/apikey",
               "budget": 60000},
    "groq": {"label": "Groq", "kind": "openai", "base_url": "https://api.groq.com/openai/v1",
             "needs_key": True, "suggested": "openai/gpt-oss-20b", "key_url": "https://console.groq.com/keys",
             "budget": 20000},
    "ollama": {"label": "Ollama (local)", "kind": "openai", "base_url": "http://127.0.0.1:11434/v1",
               "needs_key": False, "suggested": "qwen3:4b", "key_url": "https://ollama.com/download",
               "budget": 6000},
    "lmstudio": {"label": "LM Studio (local)", "kind": "openai", "base_url": "http://127.0.0.1:1234/v1",
                 "needs_key": False, "suggested": "", "key_url": "https://lmstudio.ai", "budget": 6000},
    "custom": {"label": "Otro compatible con OpenAI", "kind": "openai", "base_url": "",
               "needs_key": False, "suggested": "", "key_url": "", "budget": 20000},
}


def build_provider(provider_id: str, model: str, base_url: str = "", api_key: str | None = None) -> Provider:
    spec = PROVIDERS.get(provider_id)
    if not spec:
        raise LLMError(f"Proveedor desconocido: {provider_id}")
    key = get_secret(api_key_name(provider_id)) if api_key is None else api_key
    if spec["needs_key"] and not key:
        raise LLMError(f"Falta la API key de {spec['label']}.")
    model = model or spec["suggested"]
    if spec["kind"] == "anthropic":
        return AnthropicProvider(key, model)
    url = base_url if provider_id == "custom" else spec["base_url"]
    if not url:
        raise LLMError("Falta la URL del servidor compatible con OpenAI.")
    return OpenAICompatProvider(provider_id, spec["label"], url, key, model)


__all__ = ["PROVIDERS", "build_provider", "LLMError", "Message", "Provider", "ToolCall", "ToolResult", "ToolSpec"]
