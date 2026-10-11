<div align="center">

<img src="docs/media/hero.png" alt="Elissa, a small indigo character with a coral face and big eyes, glowing on a dark desktop" width="100%">

# Elissa

**A voice assistant with a face, living on your Windows desktop: it works with any AI model, in the cloud or on your own PC.**

[![Release](https://img.shields.io/github/v/release/inginddie/elissa?include_prereleases&label=release&color=7fe6ea)](https://github.com/inginddie/elissa/releases)
![Windows 10/11](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4?logo=windows&logoColor=white)
![Tauri 2](https://img.shields.io/badge/Tauri-2-FFC131?logo=tauri&logoColor=black)
![Python 3.13](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
[![Build](https://img.shields.io/github/actions/workflow/status/inginddie/elissa/release.yml?label=build)](https://github.com/inginddie/elissa/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-f26d5b)](LICENSE)

[Install](#install) · [Features](#what-she-can-do) · [Privacy](#privacy-and-security) · [Roadmap](#roadmap) · [Development](#development)

</div>

---

Press <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>Space</kbd> from any app and talk. Elissa listens, thinks and answers out loud.
She can read your documents, search the web, check your email and remember what you talked about.
You choose the brain: OpenAI, Claude, Gemini, OpenRouter, Groq, or a free local model with Ollama.
When you are not talking to her, she rests as a small character in the corner of your screen.

> **Status:** early preview (0.2). The interface speaks Spanish for now; English is on the [roadmap](#roadmap).

## Meet Elissa

<p align="center"><img src="docs/media/expressions.png" alt="Fourteen expressions: idle, listening, thinking, working, speaking, happy, needs you, oops, sleeping, poked, dizzy, love, surprised and waking up" width="100%"></p>

Elissa is drawn in code, not stitched from images, so she blends smoothly from one expression to the next.

- She follows your cursor across the whole desktop and blinks.
- She perks up her ears when she listens and moves her mouth with her voice.
- She shows a gear while she works and a question mark when she needs you.
- Poke her (right click) and she gets annoyed; three pokes and she gets dizzy. Rest the pointer on her and she sends hearts.
- After five quiet minutes she falls asleep, and she wakes up when you come back.

<img src="docs/media/app-listening.png" alt="Elissa's window while listening: the character with her ears up, sound waves and the talk controls" width="300" align="right">

**She stays out of your way.**
- She is a small floating bubble that grows into a card while you talk and shrinks back when she is done.
- Drag her anywhere; she expands from that corner.
- She lives in the system tray, can start with Windows and updates herself.
- She uses under 1% CPU at rest. The microphone is only on while she listens.

<br clear="right">

## What she can do

| | |
|---|---|
| 🗣️ **Talk** | Voice in, voice out, with natural Microsoft Edge voices. Interrupt her at any time, or keep the conversation going hands-free. |
| 📄 **Read your files** | Find and read PDF, Word, Excel, CSV, text and code in the folders you allow: "summarize the PDF I just downloaded". |
| 🌐 **Search the web** | Search and read pages, with no extra API key. |
| ✉️ **Check your email** | Read-only IMAP for Gmail, Outlook, Yahoo and iCloud: search, read and save attachments. She never sends, deletes or marks anything. |
| 🧠 **Remember** | Each conversation is summarized into plain Markdown notes she can recall later: "what did we talk about yesterday?" |
| 🔌 **Any model** | Switch providers in a guided setup that tests your key and lists the models your account can use. |

### Supported AI providers

| Provider | Key needed | Notes |
|---|---|---|
| OpenAI | ✔ | GPT models |
| Anthropic | ✔ | Claude models, through the official SDK |
| Google Gemini | ✔ | |
| OpenRouter | ✔ | Hundreds of models behind one key |
| Groq | ✔ | Very fast; also the recommended speech-to-text option |
| Ollama | — | Free and 100% local |
| LM Studio | — | Free and 100% local |
| Any OpenAI-compatible server | optional | Point Elissa at its URL |

## Install

1. Download `Elissa_x.y.z_x64-setup.exe` from the [latest release](https://github.com/inginddie/elissa/releases).
2. Run it. No administrator rights are needed.
3. Pick an AI provider and paste your API key, or choose Ollama to run everything locally.
4. To talk to her, open *Settings → Voice* and add a [Groq](https://console.groq.com/keys) or OpenAI key for speech
   recognition, or point her at your own Whisper server.

The installer is not code-signed yet, so Windows SmartScreen may warn you the first time. Choose *More info → Run anyway*.

**Requirements:** Windows 10 (1809+) or Windows 11, 64-bit, with WebView2 (built into Windows 11), a microphone and speakers.

### Everyday use

| Action | How |
|---|---|
| Talk | <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>Space</kbd> anywhere, or click Elissa |
| Interrupt | The same shortcut while she thinks or speaks |
| Stop talking | <kbd>Esc</kbd> in her window |
| Type instead | Chat button |
| Move | Drag her by the face |
| Hide | The ⌄ button or the tray icon; the shortcut brings her back |
| Make her sound different | *Settings → Sounds*: volume, or drop your own `listen.wav`, `done.mp3`… in the sounds folder |

## Privacy and security

- **Your keys stay in Windows.** API keys and the email password are stored in the Windows Credential Manager, never in files.
- **Your data is yours.** Settings, memory and logs live in `%APPDATA%\Elissa` as readable Markdown and JSON.
  Uninstalling does not delete them.
- **Only what you choose leaves your PC.**
  - What you say goes to the AI provider you picked.
  - Your voice audio goes to the speech service you picked.
  - Nothing else leaves your PC, and there is no telemetry.
  - With Ollama and a local Whisper server, nothing leaves your PC at all.
- **Her engine is locked to her window.**
  - The local engine accepts only Elissa's own window, through a per-session token and an origin check.
  - A web page open in your browser cannot drive her.
- **Microphone:** the microphone only opens while she listens, and she releases it a few seconds later.
- **Read-only for now.** Actions that change things, such as sending an email, editing a file or clicking in an app,
  are coming. Each one will show you exactly what will happen and wait for your click. Voice can never approve.

## Roadmap

| Phase | | Status |
|---|---|---|
| Native window, tray, signed auto-updates | F1 | ✅ |
| Character, animations, sounds | F2 | ✅ |
| Actions with approval cards: open apps and sites, timers, tasks, send email, edit files, use the computer | F4 | 🔜 |
| Voice: "Hola Elissa" wake word, local speech recognition | F3 | |
| Coding assistant: understand projects, edit with diffs, run commands | F5 | |
| Integrations through MCP: Jira, Confluence, GitHub, calendars | F6 | |
| English UI, signed installer, 1.0 | F7 | |

The detailed plan is in [`docs/PLAN.md`](docs/PLAN.md) (Spanish) and the release notes in [`CHANGELOG.md`](CHANGELOG.md).

## Development

You need [uv](https://docs.astral.sh/uv/), Node 22 and [Rust](https://rustup.rs/).

```powershell
uv sync
cd desktop; npm install; npx tauri dev    # the full app; the shell starts the Python engine with uv
uv run python -m elissa --browser         # the engine alone, with the UI in your browser
uv run pytest -q                          # tests (no network, no API keys)
powershell -File packaging\build.ps1      # engine (PyInstaller) + installer (Tauri/NSIS) into dist\
```

### Architecture

```
┌──────────────── Elissa.exe (Tauri 2, Rust) ─────────────────┐
│ transparent window · tray · global shortcut · autostart     │
│ signed updates · global cursor feed · mic permission        │
│   └─ WebView2 ── UI: character (canvas), sounds (Web Audio) │
└───────────────┬─────────────────────────────────────────────┘
                │ HTTP + WebSocket on 127.0.0.1, per-session token
┌───────────────┴─────── elissa-engine.exe (Python) ──────────┐
│ agent loop (streaming, tools, interruption, compaction)     │
│ providers: OpenAI-compatible · Anthropic SDK                │
│ tools: files · web · email (IMAP) · memory                  │
│ speech: Edge TTS out · Groq / OpenAI / Whisper in           │
└─────────────────────────────────────────────────────────────┘
```

| Path | What lives there |
|---|---|
| `desktop/` | The native shell (Rust): window modes, tray, updater, engine lifecycle |
| `elissa/server.py` | Local API, WebSocket turns, speech, setup wizard |
| `elissa/agent.py` | Provider-neutral agent loop |
| `elissa/llm/` | Provider adapters; adding an OpenAI-compatible provider is one entry in `PROVIDERS` |
| `elissa/tools/` | Files, web and email tools with their JSON schemas |
| `elissa/memory.py` | Long-term memory as Markdown |
| `elissa/static/` | UI: `character.js` (Elissa), `sounds.js`, window modes, settings |
| `design/` | Character references (generated with Nano Banana 2) and previews |

## Contributing

Issues and pull requests are welcome. Please run `uv run pytest -q` before sending changes, and keep the security rules:
- Secrets only in the Credential Manager.
- No telemetry.
- Every action that changes something waits for an explicit click.

## License

[MIT](LICENSE) © 2026 Diego Bustos
