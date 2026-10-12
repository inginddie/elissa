# First steps

## 1. Set up your AI

The first time, Elissa opens **Set up your AI**:

1. Pick a **provider**. Ollama and LM Studio run on your computer and need no key.
2. Paste your **API key**. *Where do I get it?* takes you to the provider's page.
3. Choose **Connect and list models**. Elissa tests the key and lists the models your account can use.
4. Pick a **model** (one is suggested) and choose **Save and test**.

| Provider | Key | Notes |
|---|:-:|---|
| OpenAI | :material-check: | GPT models |
| Anthropic | :material-check: | Claude models |
| Google Gemini | :material-check: | |
| OpenRouter | :material-check: | Hundreds of models behind one key |
| Groq | :material-check: | Very fast; also the recommended speech service |
| Ollama | — | Free and 100% local. [Install Ollama](https://ollama.com) first |
| LM Studio | — | Free and 100% local. [Install LM Studio](https://lmstudio.ai) first |
| Other OpenAI-compatible server | optional | Point Elissa at its URL |

Your key is stored in your system's keychain (Windows Credential Manager, macOS Keychain or Linux Secret Service),
never in a file. You can change provider or model later in *Settings → Artificial intelligence*.

## 2. Let her hear you

Open *Settings* (the gear) → **Voice** → **Speech recognition**, and pick how she understands you:

- **Groq**: very fast and cheap, free to start. Paste a [Groq key](https://console.groq.com/keys).
- **OpenAI**: paste an [OpenAI key](https://platform.openai.com/api-keys).
- **On your PC** (Windows): private and offline. Downloads whisper.cpp and a 60 MB model once.
- **Your own server**: any Whisper-compatible transcription URL.

With **Automatic**, Elissa uses whatever is available: your chat provider's own speech service, any Groq or OpenAI key
you saved, your server, or on-PC recognition if it's installed.

## 3. Talk

| Action | How |
|---|---|
| Talk | Say "Hey Elissa" / "Hola Elissa", press ++ctrl+alt+space++ anywhere, click her face, or press ++space++ in her window |
| Interrupt her | The same shortcut while she thinks or speaks, or just talk if *Interrupt her by talking* is on |
| Stop | ++esc++ in her window |
| End the conversation | "Thanks, that's all", "bye", "listo, gracias" |
| Type instead | The chat button |
| Move her | Drag her by the face |
| Hide her | The ⌄ button, the tray icon, or say "hide"; the shortcut brings her back |
| Give her a file | Drop it on her window and ask about it |

With **Continuous conversation** on (the default), she listens again after each answer, so you can keep talking
without the shortcut.

To wake her by voice, turn on the wake phrase in *Settings → Voice*. The first time it downloads a 40 MB model; after
that it works offline and pauses while your screen is locked.

## 4. Approve what she does

When Elissa wants to change something (write a file, send an email, run a command, click in a window) she shows an
**approval card** with exactly what will happen: the diff, the full email, the command as it will run. Only a real
click on the card approves it. Your voice, the shortcut and the AI can't. ++esc++ denies it.

Reading things (files in your allowed folders, the web, your email if you enabled it) doesn't need a card.

## 5. Make her yours

- *Settings → General*: her name, your name, and the interface language (Spanish or English).
- *Settings → Voice*: her voice and speed, and whether to start with your system.
- *Settings → Folders she can use*: by default, your home folder.
- *Settings → Sounds*: volume, or [your own sounds](settings.md#sounds).

Next: [everything you can ask her](voice-commands.md).
