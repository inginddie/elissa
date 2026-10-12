# Contributing to Elissa

Thanks for helping! Issues, ideas and pull requests are welcome.

## Getting started

You need [uv](https://docs.astral.sh/uv/), Node 22 and [Rust](https://rustup.rs/) on Windows 10/11.

```powershell
uv sync
cd desktop; npm install; npx tauri dev    # the full app (the shell starts the Python engine with uv)
uv run python -m elissa --browser         # just the engine, with the UI in your browser
uv run pytest -q                          # tests (no network, no API keys)
```

`tests/smoke_ws.py` runs a real turn against a running engine, and can answer approval cards. That makes it handy
for trying a change end to end without clicking.

## Where things live

| Path | What |
|---|---|
| `desktop/` | Native shell (Tauri 2, Rust): window modes, tray, global shortcut, updater, engine lifecycle |
| `elissa/server.py` | Local API and WebSocket, speech, setup wizard, approvals |
| `elissa/agent.py` | Provider-neutral agent loop and the system prompt |
| `elissa/tools/` | Tools; anything that changes something has a `preview` and goes through approval |
| `elissa/mcp_client.py` | MCP integrations |
| `elissa/wake.py`, `local_stt.py`, `windows_tts.py`, `edge_voice.py` | Voice |
| `elissa/static/` | UI: `character.js` (Elissa), `sounds.js`, `i18n.js`, `app.js` |
| `docs/PLAN.md` | Roadmap and backlog (Spanish) |

## Ground rules

- **Safety first.**
  - A tool that sends, writes, moves, clicks, types or runs anything must have a `preview` that shows exactly what
    will happen.
  - Nothing may delete user data.
  - Read [SECURITY.md](SECURITY.md) before touching tools, approvals or the engine API.
- **Secrets only in the Credential Manager** (`elissa.config.set_secret`). Never in settings, logs or the repo.
- **No telemetry.** Network calls only to services the user configured.
- **Tests:** add one for each behaviour you change. Everything in `tests/` must pass without network or keys.
- **UI text:**
  - The UI is written in Spanish.
  - Add the English for any new string to `elissa/static/i18n.js`, and wrap dynamic strings in `t()`.
- **Style:** follow the code around you. Comments explain *why*.

## Releasing (maintainers)

1. Bump the version in `elissa/__init__.py`, `pyproject.toml`, `desktop/src-tauri/Cargo.toml` and
   `desktop/src-tauri/tauri.conf.json`.
2. Update `CHANGELOG.md`.
3. Tag `vX.Y.Z`. CI tests the code, builds and self-tests the engine, and builds the signed installer as a draft
   release.
4. Publish the release as **latest**, not as a pre-release. The updater reads `/releases/latest`.
