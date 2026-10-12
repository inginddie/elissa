"""Alerts from Claude Code / Codex hooks: event parsing, installing without touching the rest, the endpoint."""
import json
import os
import sys
import tempfile

os.environ["ELISSA_HOME"] = os.environ.get("ELISSA_HOME") or tempfile.mkdtemp()  # before importing elissa

import pytest

from elissa import agent_hooks


@pytest.fixture
def homes(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_hooks, "CLAUDE_SETTINGS", tmp_path / ".claude" / "settings.json")
    monkeypatch.setattr(agent_hooks, "CODEX_HOOKS", tmp_path / ".codex" / "hooks.json")
    monkeypatch.setattr(agent_hooks, "_last", {})
    return tmp_path


def test_parse_events():
    p = agent_hooks.parse_event
    assert p({"source": "claude", "event": "Stop", "cwd": r"C:\code\elissa"}, now=0) == {
        "source": "claude", "label": "Claude Code", "kind": "done", "project": "elissa"}
    assert p({"source": "claude", "event": "Notification", "type": "permission_prompt", "cwd": "C:\\x\\"},
             now=0)["kind"] == "permission"
    assert p({"source": "codex", "event": "PermissionRequest", "cwd": "/w/app"}, now=0)["kind"] == "permission"
    assert p({"source": "claude", "event": "Notification", "type": "idle_prompt", "cwd": ""}, now=0)["kind"] == "waiting"
    assert p({"source": "claude", "event": "Notification", "type": "auth_success"}, now=0) is None
    assert p({"source": "other", "event": "Stop"}, now=0) is None
    assert p({"source": "claude", "event": "PreToolUse"}, now=0) is None


def test_same_alert_is_not_repeated_at_once(homes):
    e = {"source": "codex", "event": "Stop", "cwd": "C:\\a"}
    assert agent_hooks.parse_event(e, now=100)
    assert agent_hooks.parse_event(e, now=101) is None
    assert agent_hooks.parse_event(e, now=106)


def test_install_keeps_the_rest_and_is_idempotent(homes):
    path = agent_hooks.CLAUDE_SETTINGS
    path.parent.mkdir(parents=True)
    mine = {"type": "command", "command": "node block.js"}
    original = {"model": "opus", "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [mine]}],
                                           "Stop": [{"hooks": [mine]}]}}
    path.write_text(json.dumps(original), "utf-8")

    agent_hooks.set_installed("claude", True)
    agent_hooks.set_installed("claude", True)
    data = json.loads(path.read_text("utf-8"))
    assert data["model"] == "opus" and data["hooks"]["PreToolUse"] == original["hooks"]["PreToolUse"]
    assert len(data["hooks"]["Stop"]) == 2 and data["hooks"]["Stop"][0]["hooks"] == [mine]
    ours = data["hooks"]["Stop"][1]["hooks"][0]
    assert ours["command"] == agent_hooks._command()[0] and ours["async"] is True and ours["args"][-1] == "claude"
    assert agent_hooks.installed("claude")
    assert json.loads(path.with_name("settings.json.elissa-backup").read_text("utf-8")) == original

    agent_hooks.set_installed("claude", False)
    assert json.loads(path.read_text("utf-8")) == original
    assert not agent_hooks.installed("claude")


def test_codex_install_from_scratch(homes):
    agent_hooks.set_installed("codex", True)
    data = json.loads(agent_hooks.CODEX_HOOKS.read_text("utf-8"))
    assert set(data["hooks"]) == {"Stop", "PermissionRequest"}
    handler = data["hooks"]["Stop"][0]["hooks"][0]
    assert handler["command"].endswith(" codex") and ("commandWindows" in handler) == (sys.platform == "win32")
    agent_hooks.set_installed("codex", False)
    assert json.loads(agent_hooks.CODEX_HOOKS.read_text("utf-8")) == {}


@pytest.mark.skipif(not agent_hooks.system.has("agent_hooks"), reason="no hook script on this system yet")
def test_endpoint_needs_the_hook_token():
    from fastapi.testclient import TestClient

    from elissa.server import app
    with TestClient(app) as client:
        assert client.post("/hooks/agent-event", json={"source": "claude", "event": "Stop"}).status_code == 403
        r = client.post("/hooks/agent-event", json={"source": "claude", "event": "Stop", "cwd": "C:\\p"},
                        headers={"X-Elissa-Hook": agent_hooks.TOKEN})
        assert r.status_code == 200
        assert client.get("/api/agent-hooks").status_code == 403  # settings stay behind the session cookie
        # notify.sh passes the hook's own JSON; only event, type and folder are used
        raw = {"hook_event_name": "Notification", "notification_type": "permission_prompt", "cwd": "/Users/d/web",
               "message": "x" * 50000}
        r = client.post("/hooks/agent-event", json=raw, headers={"X-Elissa-Hook": agent_hooks.TOKEN,
                                                                 "X-Elissa-Source": "codex"})
        assert r.status_code == 200
        endpoint = json.loads(agent_hooks.ENDPOINT_FILE.read_text("utf-8"))
        assert endpoint["token"] == agent_hooks.TOKEN and agent_hooks.SCRIPT.exists()


def test_users_own_notify_script_is_left_alone(homes):
    path = agent_hooks.CLAUDE_SETTINGS
    path.parent.mkdir(parents=True)
    theirs = {"type": "command", "command": "powershell.exe", "args": ["-File", r"C:\Users\u\.claude\hooks\notify.ps1"]}
    path.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [theirs]}]}}), "utf-8")
    assert not agent_hooks.installed("claude")
    agent_hooks.set_installed("claude", True)
    agent_hooks.set_installed("claude", False)
    assert json.loads(path.read_text("utf-8")) == {"hooks": {"Stop": [{"hooks": [theirs]}]}}


def test_raw_hook_is_reduced():
    raw = {"hook_event_name": "Stop", "cwd": "/Users/d/elissa", "last_assistant_message": "secret", "session_id": "s"}
    assert agent_hooks.from_raw_hook(raw, "claude") == {"source": "claude", "event": "Stop", "type": "",
                                                        "cwd": "/Users/d/elissa"}
