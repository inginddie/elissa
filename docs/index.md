---
hide:
  - navigation
---

# Elissa

<div class="hero" markdown>
![Elissa, a small indigo character with a coral face and big eyes, glowing on a dark desktop](media/hero.png){ .skip-lightbox }
</div>

**A voice assistant with a face, living on your desktop.** Say "Hey Elissa" or press ++ctrl+alt+space++, and talk.
She answers out loud, with any AI model, and nothing changes without your click.

[Install Elissa](install.md){ .md-button .md-button--primary }
[First steps](first-steps.md){ .md-button }

## How it works

<figure class="shot" markdown>
![Elissa answering a question out loud, with the question and her answer written below her](media/screens/en/reply.png)
</figure>

```mermaid
flowchart TB
  A["🗣️ You talk"] --> B["👂 She understands<br>(speech to text)"]
  B --> C["🧠 Your AI thinks"]
  C --> D{"Changes<br>something?"}
  D -- no --> E["🔊 She answers"]
  D -- yes --> F["✋ Approval card"]
  F -- your click --> E
```

Reading, searching and answering happen on their own. Writing, sending, clicking or running anything shows you a
card first, and only your click approves it.

## What she can do

<div class="grid cards" markdown>

- :material-account-voice: **Talk**, hands-free, and interrupt her any time
- :material-brain: **Any AI**: OpenAI, Claude, Gemini, OpenRouter, Groq, or free and local with Ollama
- :material-file-document: **Your files**: read PDF, Word, Excel; write with a diff; never delete
- :material-monitor: **Your computer**: open apps and sites; on Windows, use other windows
- :material-alarm: **Timers, reminders and tasks**
- :material-email: **Email**: search, read, and send with your OK
- :material-code-braces: **Code**: understand a project, edit, run your tests
- :material-spotify: **Music**: Spotify, pause, skip, volume
- :material-puzzle: **Integrations**: GitHub, Jira, Confluence, Google Calendar
- :material-bell: **Claude Code and Codex alerts**
- :material-head-lightbulb: **Memory**: "what did we talk about yesterday?"
- :material-shield-check: **Private**: no account, no telemetry

</div>

[Everything you can ask her](voice-commands.md){ .md-button }

## Meet Elissa

![Fourteen expressions: idle, listening, thinking, working, speaking, happy, needs you, oops, sleeping, poked, dizzy, love, surprised and waking up](media/expressions.png)

She follows your cursor, perks up her ears when she listens and shows a gear while she works. Poke her (right click)
and she gets annoyed; rest the pointer on her and she sends hearts.

## Systems

| | Windows 10 / 11 | macOS 11+ (Apple Silicon) | Linux |
|---|:-:|:-:|:-:|
| Status | Full | Preview | Preview |

[What works on each system](install.md#what-works-on-each-system) ·
[Privacy policy](privacy.md) · [Security](security.md) · [Code signing policy](code-signing.md)
