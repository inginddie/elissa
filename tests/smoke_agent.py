"""Manual smoke test: run one agent turn against a real provider. Usage: python tests/smoke_agent.py <provider> <model> "<question>" """
import asyncio, os, sys, tempfile, time
os.environ.setdefault("ELISSA_HOME", tempfile.mkdtemp())
from elissa.agent import Agent
from elissa.llm import build_provider
from elissa.memory import Memory, register as reg_memory
from elissa.tools import ToolRegistry
from elissa.tools.files import FileTools, register as reg_files
from elissa.tools.web import register as reg_web

prov_id, model, question = sys.argv[1], sys.argv[2], sys.argv[3]
settings = {"name": "Elissa", "user_name": "Diego", "allowed_folders": [os.path.expanduser("~")]}
provider = build_provider(prov_id, model)
reg = ToolRegistry(); reg_files(reg, FileTools(lambda: settings["allowed_folders"])); reg_web(reg)
memory = Memory(lambda: provider); reg_memory(reg, memory)
agent = Agent(lambda: settings, lambda: provider, reg, lambda: 6000)

async def emit(ev):
    if ev["type"] == "tool": print(f"\n  [tool] {ev['tool']}", flush=True)
    elif ev["type"] == "delta": print(ev["text"], end="", flush=True)

async def main():
    t = time.time()
    await agent.run_turn(question, emit)
    print(f"\n-- {time.time()-t:.1f}s, {len(agent.history)} mensajes en historial")
asyncio.run(main())
