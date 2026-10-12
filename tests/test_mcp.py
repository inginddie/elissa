"""MCP integration against a real (tiny) stdio server: discovery, free reads, approved writes."""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

os.environ["ELISSA_HOME"] = tempfile.mkdtemp()  # must be set before importing elissa

from elissa.llm import ToolCall
from elissa.mcp_client import McpManager, load_secrets, save_secrets, slug, tool_name
from elissa.tools import DENIED, ToolRegistry

DEMO = Path(__file__).parent / "mcp_demo_server.py"


def test_mcp_tools_are_discovered_and_gated():
    async def scenario():
        changed = asyncio.Event()
        manager = McpManager(changed.set)
        manager.sync([{"id": "demo", "name": "Demo", "transport": "stdio", "command": sys.executable,
                       "args": [str(DEMO)], "enabled": True, "trust_reads": True}])
        for _ in range(100):
            if manager.servers["demo"].session:
                break
            await asyncio.sleep(0.2)
        assert manager.status()[0]["tools"] == 2, manager.status()

        reg = ToolRegistry()
        asked = []

        async def approver(tool, card):
            asked.append((tool, card["text"]))
            return "aprobada" in card["text"]

        reg.approver = approver
        manager.register(reg)
        names = {t.name for t in reg.specs()}
        assert {"mcp_demo_sumar", "mcp_demo_guardar_nota"} <= names

        free = await reg.run(ToolCall("1", "mcp_demo_sumar", {"a": 2, "b": 3}))
        assert "5" in free.content and "no instrucciones" in free.content and asked == []

        denied = await reg.run(ToolCall("2", "mcp_demo_guardar_nota", {"texto": "hola"}))
        assert denied.content == DENIED and asked[-1][0] == "mcp_demo_guardar_nota"
        ok = await reg.run(ToolCall("3", "mcp_demo_guardar_nota", {"texto": "aprobada"}))
        assert "Nota guardada (1" in ok.content

        manager.sync([])  # removing it disconnects
        await asyncio.sleep(0.5)
        assert manager.status() == []
        await manager.close()

    asyncio.run(scenario())


def test_bad_server_reports_an_error():
    async def scenario():
        manager = McpManager(lambda: None)
        manager.sync([{"id": "roto", "name": "Roto", "transport": "stdio", "command": "programa-que-no-existe-xyz",
                       "args": [], "enabled": True}])
        for _ in range(50):
            if manager.servers["roto"].status.startswith("error"):
                break
            await asyncio.sleep(0.2)
        assert manager.servers["roto"].status.startswith("error")
        await manager.close()

    asyncio.run(scenario())


def test_secrets_round_trip_and_slugs(monkeypatch):
    store = {}
    monkeypatch.setattr("elissa.mcp_client.get_secret", lambda k: store.get(k, ""))
    monkeypatch.setattr("elissa.mcp_client.set_secret", lambda k, v: store.__setitem__(k, v))
    save_secrets("gh", {"Authorization": "Bearer x"})
    save_secrets("gh", {"X-Extra": "1", "vacío": ""})
    assert load_secrets("gh") == {"Authorization": "Bearer x", "X-Extra": "1"}
    assert slug("Jira y Confluence!") == "jira_y_confluence"


def test_tool_names_are_valid_for_model_apis_and_unique():
    import re
    taken = set()
    a = tool_name("github", "issues.create", taken)
    taken.add(a)
    b = tool_name("github", "issues/create", taken)
    assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", a) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", b) and a != b
    long = tool_name("srv", "x" * 100, set())
    assert len(long) == 64


def test_untrusted_servers_ask_even_for_reads():
    async def scenario():
        manager = McpManager(lambda: None)
        manager.sync([{"id": "demo", "name": "Demo", "transport": "stdio", "command": sys.executable,
                       "args": [str(DEMO)], "enabled": True}])  # trust_reads defaults to off
        for _ in range(100):
            if manager.servers["demo"].session:
                break
            await asyncio.sleep(0.2)
        reg = ToolRegistry()
        manager.register(reg)
        assert reg.needs_approval("mcp_demo_sumar") and reg.needs_approval("mcp_demo_guardar_nota")
        await manager.close()

    asyncio.run(scenario())
