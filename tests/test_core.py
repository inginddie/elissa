"""Core tests with a fake LLM provider: no network, no API keys, no audio."""
import asyncio
import os
import tempfile
from pathlib import Path

os.environ["ELISSA_HOME"] = tempfile.mkdtemp()  # must be set before importing elissa

import pytest

from elissa.agent import Agent
from elissa.llm import Message, ToolCall
from elissa.memory import Memory
from elissa.server import SentenceSplitter, speakable
from elissa.tools import ToolRegistry
from elissa.tools.files import FileTools, register as register_files


class FakeProvider:
    """Replays scripted assistant messages; records what it was sent."""
    id = "fake"

    def __init__(self, script):
        self.script = list(script)
        self.seen = []

    async def stream(self, system, history, tools, on_text):
        self.seen.append(list(history))
        msg = self.script.pop(0)
        if msg.text:
            await on_text(msg.text)
        return msg

    async def complete(self, system, prompt):
        return '{"titulo": "Prueba", "resumen": "Se probó.", "recuerdos": [{"archivo": "color", "name": "título", ' \
               '"description": "", "type": "preferencia", "contenido": "Le gusta el verde."}]}'

    async def list_models(self):
        return ["fake-1"]


def make_agent(provider, folder):
    reg = ToolRegistry()
    register_files(reg, FileTools(lambda: [str(folder)]))
    return Agent(lambda: {"name": "Elissa", "user_name": "Ana"}, lambda: provider, reg, lambda: 6000)


async def collect(agent, text):
    events = []

    async def emit(ev):
        events.append(ev)

    reply = await agent.run_turn(text, emit)
    return reply, events


def test_agent_runs_tool_and_answers(tmp_path):
    (tmp_path / "nota.txt").write_text("La clave del wifi es pez-azul", "utf-8")
    provider = FakeProvider([
        Message("assistant", text="Voy a mirar.", tool_calls=[ToolCall("c1", "leer_archivo", {"path": str(tmp_path / "nota.txt")})]),
        Message("assistant", text="Es pez-azul."),
    ])
    agent = make_agent(provider, tmp_path)
    reply, events = asyncio.run(collect(agent, "¿cuál es la clave del wifi?"))
    assert reply == "Voy a mirar.\nEs pez-azul."
    assert [m.role for m in agent.history] == ["user", "assistant", "tool", "assistant"]
    assert "pez-azul" in agent.history[2].results[0].content
    assert any(e["type"] == "tool" for e in events)


def test_file_tools_refuse_outside_allowed_folders(tmp_path):
    files = FileTools(lambda: [str(tmp_path)])
    with pytest.raises(PermissionError):
        files.resolve(str(Path(tmp_path).parent))
    (tmp_path / ".env").write_text("SECRET=1")
    with pytest.raises(PermissionError):
        files.resolve(str(tmp_path / ".env"))


def test_interrupted_turn_leaves_valid_history(tmp_path):
    class SlowProvider(FakeProvider):
        async def stream(self, system, history, tools, on_text):
            await on_text("Estoy pen")
            await asyncio.sleep(10)

    agent = make_agent(SlowProvider([]), tmp_path)

    async def scenario():
        task = asyncio.create_task(collect(agent, "hola"))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert [m.role for m in agent.history] == ["user", "assistant"]
    assert agent.history[-1].text.startswith("Estoy pen")


def test_memory_consolidation_writes_indexes():
    provider = FakeProvider([])

    async def scenario():
        mem = Memory(lambda: provider)
        mem.record("user", "Recuerda que me gusta el verde")
        mem.record("assistant", "Anotado.")
        await mem.close()
        return mem

    asyncio.run(scenario())
    from elissa.memory import CONV_INDEX, FACTS, INDEX
    assert "Prueba" in CONV_INDEX.read_text("utf-8")
    assert "(hechos/color.md)" in INDEX.read_text("utf-8")
    assert "Color" in INDEX.read_text("utf-8")  # placeholder title "título" replaced
    assert "verde" in (FACTS / "color.md").read_text("utf-8")


def test_sentence_splitter_and_speakable():
    s = SentenceSplitter(min_len=10)
    out = s.feed("Hola Diego, **todo** bien. Revisé tu correo y ")
    assert out == ["Hola Diego, todo bien."]
    assert s.flush() == ["Revisé tu correo y"]
    assert speakable("Mira [esto](https://x.y) en https://a.b") == "Mira esto en el enlace"


def test_memory_title_ignores_echoed_template(tmp_path):
    class EchoProvider(FakeProvider):
        async def complete(self, system, prompt):
            return '{"titulo": "título corto y específico (máx. 8 palabras)", "resumen": "x", "recuerdos": []}'

    async def scenario():
        mem = Memory(lambda: EchoProvider([]))
        mem.record("user", "¿Cuál es la TRM de hoy?")
        mem.record("assistant", "Está en 4.000.")
        await mem.close()

    asyncio.run(scenario())
    from elissa.memory import CONV_INDEX
    index = CONV_INDEX.read_text("utf-8")
    assert "máx" not in index
    assert "TRM de hoy" in index


def test_memory_drops_template_echoes_and_assistant_state():
    from elissa.memory import _is_noise
    assert _is_noise({"archivo": "slug-kebab-case", "name": "x", "contenido": "y"})
    assert _is_noise({"archivo": "correo", "name": "Correo no configurado",
                      "contenido": "No hay cuentas de correo configuradas en el dispositivo."})
    assert _is_noise({"archivo": "quien-soy", "name": "¿Quién soy?", "contenido": "Mi nombre es Elissa y soy asistente."})
    assert not _is_noise({"archivo": "usuario-diego", "name": "Nombre", "contenido": "El usuario se llama Diego."})
    assert not _is_noise({"archivo": "mama", "name": "Mamá", "contenido": "La mamá de Diego no tiene correo."})


def test_system_prompt_states_current_capabilities():
    reg = ToolRegistry()
    reg.add("buscar_correos", "x", "x", lambda: "", {})
    agent = Agent(lambda: {"mail_user": "yo@gmail.com", "allowed_folders": ["C:/Users/yo"]}, lambda: None, reg,
                  lambda: 1000)
    prompt = agent.system_prompt()
    assert "Correo: conectado (yo@gmail.com)" in prompt and "manda sobre cualquier recuerdo" in prompt


def test_retired_models_are_replaced_on_load():
    from elissa import config
    config.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.SETTINGS_FILE.write_text('{"provider": "groq", "model": "llama-3.3-70b-versatile"}', "utf-8")
    try:
        assert config.load_settings()["model"] == "openai/gpt-oss-120b"
        config.SETTINGS_FILE.write_text('{"provider": "openai", "model": "gpt-4.1"}', "utf-8")
        assert config.load_settings()["model"] == "gpt-4.1"
    finally:
        config.SETTINGS_FILE.unlink()


def test_reasoning_off_only_where_needed():
    from elissa.llm.openai_provider import reasoning_params
    off = {"reasoning_effort": "none"}
    assert reasoning_params("gpt-6-luna") == off
    assert reasoning_params("openai/gpt-6-luna") == off
    assert reasoning_params("qwen3:4b") == off
    assert reasoning_params("qwen2.5:3b") == {}
    assert reasoning_params("openai/gpt-oss-20b") == {}
