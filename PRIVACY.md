# Privacy policy

Elissa runs on your computer. It has no account, no server of its own and no telemetry. Your settings, memory and
logs stay on your computer as readable Markdown and JSON (in `%APPDATA%\Elissa` on Windows,
`~/Library/Application Support/Elissa` on macOS and `~/.local/share/Elissa` on Linux), and your keys stay in your
system's keychain (Windows Credential Manager, macOS Keychain or Linux Secret Service).

Some features only work by contacting a service. Elissa contacts a service only for a feature you use, and only the
service you chose. Each one can be turned off.

| What leaves your PC | Where it goes | When | How to avoid it |
|---|---|---|---|
| What you say or type, the conversation, and what Elissa reads for you (files, pages, emails, windows) | The AI provider you picked (OpenAI, Anthropic, Google, Groq, OpenRouter, or your own server) | Each time you talk to her | Pick Ollama or LM Studio: the model runs on your PC |
| Your voice recordings | The speech-to-text service you picked (Groq, OpenAI or your own server) | Each time you talk to her | *Settings → Voice → On your PC* (whisper.cpp, Windows) |
| The text of her answers | Microsoft Edge's speech service | When she speaks with a natural voice | Pick an offline voice in *Settings → Voice* (Windows and macOS) |
| Web searches and pages you ask about | DuckDuckGo and those websites | When you ask her to search or read the web | Don't ask for web searches |
| Email | Your own mail server (IMAP/SMTP) | Only if you set up email | Leave email off (the default) |
| Your searches and playback commands, with your Spotify account | Spotify | Only if you connect Spotify | Don't connect it (the default) |
| Data of the integrations you connect | The MCP servers you add (for example GitHub or Atlassian) | Only if you add them | Don't add integrations |
| A version check | GitHub (this repository's releases) | When the app starts | — |
| Model downloads | alphacephei.com (wake phrase), GitHub and Hugging Face (on-PC speech recognition) | Once, when you turn those features on | Leave them off (the default) |

Those services handle your data under their own privacy policies.

**Things that never leave your PC:**
- The wake phrase. "Hey Elissa" / "Hola Elissa" is detected locally, and nothing is sent until you wake her.
- Alerts from Claude Code and Codex. The hooks only reach Elissa on your own PC.
- Your memory notes and settings.

Questions: open an issue at https://github.com/inginddie/elissa/issues.
