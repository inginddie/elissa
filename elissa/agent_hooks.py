"""Alerts from coding agents: Claude Code and Codex tell Elissa when a session finishes or needs the user.

Elissa installs, on request, a command hook in each tool (~/.claude/settings.json, ~/.codex/hooks.json) that runs
hooks/notify.ps1. The script reads the hook's JSON from stdin and posts a small event to the running engine, using
the port and a hook-only token from agent-hooks.json (rewritten on every launch). Only the event, the alert type and
the project folder's name are sent: never prompts, answers or transcripts. If Elissa is closed the script gives up at
once. It always prints "{}" and exits 0, so it can never block or steer a session.
"""
import json
import logging
import os
import secrets
import shutil
import time
from pathlib import Path

from .config import HOME

log = logging.getLogger(__name__)

ENDPOINT_FILE = HOME / "agent-hooks.json"
SCRIPT = HOME / "hooks" / "notify.ps1"
CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"
CODEX_HOOKS = Path.home() / ".codex" / "hooks.json"

SCRIPT_TEXT = r"""# Elissa: forwards Claude Code / Codex hook events to the running Elissa. Always prints {} and exits 0.
param([string]$Source = "claude")
$ErrorActionPreference = "SilentlyContinue"
try {
    $raw = [Console]::In.ReadToEnd()
    $cfg = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot "..\agent-hooks.json") | ConvertFrom-Json
    $probe = New-Object Net.Sockets.TcpClient  # Elissa closed: give up in 300 ms, not after Windows' retries
    $open = $probe.ConnectAsync("127.0.0.1", [int]$cfg.port).Wait(300) -and $probe.Connected
    $probe.Close()
    if (-not $open) { throw "Elissa is not running" }
    $evt = $raw | ConvertFrom-Json
    $body = @{ source = $Source; event = "$($evt.hook_event_name)"; type = "$($evt.notification_type)";
               cwd = "$($evt.cwd)" } | ConvertTo-Json -Compress
    Invoke-RestMethod -Uri "http://127.0.0.1:$($cfg.port)/hooks/agent-event" -Method Post -TimeoutSec 3 `
        -Headers @{ "X-Elissa-Hook" = $cfg.token } -ContentType "application/json; charset=utf-8" `
        -Body ([Text.Encoding]::UTF8.GetBytes($body)) | Out-Null
} catch {}
"{}"
exit 0
"""

SOURCES = {"claude": "Claude Code", "codex": "Codex"}
REPEAT_S = 5  # the same alert for the same project within this window is shown once

TOKEN = secrets.token_hex(16)
_last: dict[tuple, float] = {}


def publish_endpoint(port: int) -> None:
    """Writes the hook script and where to reach this engine; called on every launch."""
    SCRIPT.parent.mkdir(parents=True, exist_ok=True)
    if not SCRIPT.exists() or SCRIPT.read_text("utf-8-sig") != SCRIPT_TEXT:
        SCRIPT.write_text(SCRIPT_TEXT, "utf-8-sig")  # BOM: Windows PowerShell 5.1 reads UTF-8 only with it
    ENDPOINT_FILE.write_text(json.dumps({"port": port, "token": TOKEN}), "utf-8")


def authorized(header: str | None) -> bool:
    return bool(header) and secrets.compare_digest(header, TOKEN)


def parse_event(body: dict, now: float | None = None) -> dict | None:
    """Turns a hook post into an alert {source, label, kind, project}, or None if it is not worth one."""
    source = body.get("source")
    if source not in SOURCES or not isinstance(body.get("event"), str):
        return None
    event, kind_hint = body["event"], body.get("type") or ""
    if event == "Stop":
        kind = "done"
    elif event == "StopFailure":
        kind = "error"
    elif event == "PermissionRequest" or (event == "Notification" and kind_hint == "permission_prompt"):
        kind = "permission"
    elif event == "Notification" and kind_hint in ("idle_prompt", "agent_needs_input"):
        kind = "waiting"
    else:
        return None
    cwd = str(body.get("cwd") or "")
    project = Path(cwd.rstrip("\\/")).name[:60] if cwd else ""
    now = time.monotonic() if now is None else now
    key = (source, project, kind)
    if now - _last.get(key, -REPEAT_S) < REPEAT_S:
        return None
    _last[key] = now
    return {"source": source, "label": SOURCES[source], "kind": kind, "project": project}


# ----- installing the hooks -----

def _command() -> list[str]:
    return ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT)]


def _ours(handler: dict) -> bool:
    """Only handlers that run Elissa's own script (users often have a notify.ps1 of their own)."""
    script = str(SCRIPT).lower()
    parts = [handler.get("command"), handler.get("commandWindows"), *(handler.get("args") or [])]
    return any(isinstance(p, str) and script in p.lower() for p in parts)


def _read(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text("utf-8-sig") or "{}")
    if not isinstance(data, dict):
        raise ValueError(f"{path} no es un objeto JSON")
    return data


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_name(path.name + ".elissa-backup")
        if not backup.exists():  # keep the user's original, from before Elissa ever touched it
            shutil.copy2(path, backup)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", "utf-8")
    os.replace(tmp, path)


def _strip(hooks: dict) -> dict:
    """Removes Elissa's handlers (and groups left empty) from a {"Event": [groups]} map."""
    out = {}
    for event, groups in hooks.items():
        kept = []
        for group in groups if isinstance(groups, list) else []:
            if not isinstance(group, dict):
                kept.append(group)
                continue
            handlers = [h for h in group.get("hooks", []) if not (isinstance(h, dict) and _ours(h))]
            if handlers:
                kept.append({**group, "hooks": handlers})
        if kept:
            out[event] = kept
    return out


def _targets(tool: str) -> tuple[Path, dict]:
    if tool == "claude":
        handler = {"type": "command", "command": "powershell.exe", "args": _command()[1:] + ["claude"],
                   "async": True, "timeout": 10}
        return CLAUDE_SETTINGS, {"Stop": [{"hooks": [handler]}], "StopFailure": [{"hooks": [handler]}],
                                 "Notification": [{"matcher": "permission_prompt|idle_prompt|agent_needs_input",
                                                   "hooks": [handler]}]}
    if tool == "codex":
        line = " ".join(f'"{a}"' if " " in a else a for a in _command() + ["codex"])
        handler = {"type": "command", "command": line, "commandWindows": line, "async": True, "timeout": 10}
        return CODEX_HOOKS, {"Stop": [{"hooks": [handler]}], "PermissionRequest": [{"hooks": [handler]}]}
    raise ValueError(tool)


def installed(tool: str) -> bool:
    path, _ = _targets(tool)
    try:
        hooks = _read(path).get("hooks") or {}
    except (ValueError, OSError):
        return False
    return any(isinstance(h, dict) and _ours(h)
               for groups in hooks.values() if isinstance(groups, list)
               for g in groups if isinstance(g, dict) for h in g.get("hooks", []))


def set_installed(tool: str, on: bool) -> None:
    """Adds or removes Elissa's hooks, keeping everything else in the file as it was."""
    path, wanted = _targets(tool)
    data = _read(path)
    hooks = _strip(data.get("hooks") or {})
    if on:
        for event, groups in wanted.items():
            hooks[event] = hooks.get(event, []) + groups
    if hooks:
        data["hooks"] = hooks
    else:
        data.pop("hooks", None)
    _write(path, data)
    log.info("agent hooks for %s %s in %s", tool, "installed" if on else "removed", path)


def status() -> dict:
    return {tool: {"label": SOURCES[tool], "installed": installed(tool), "path": str(_targets(tool)[0]),
                   "detected": _targets(tool)[0].parent.exists()} for tool in SOURCES}
