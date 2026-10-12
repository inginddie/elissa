# Settings

Open *Settings* with the gear in Elissa's window or from the tray menu (*Ajustes*). It's a single panel with one
section per topic. Changes are saved as you make them.

Sections that don't apply to your system are hidden. The tray menu is in Spanish on every system.

## General

| Option | What it does | Default |
|---|---|---|
| **Language** | The interface language: *Automatic (from the system)*, *Español* or *English*. Changing it also switches her speech language and voice. | Automatic |
| **Assistant's name** | What she calls herself (up to 20 characters). | Elissa |
| **Your name** | So she calls you by your name (up to 30 characters). | — |

## Artificial intelligence

Shows the provider and model in use. **Change provider or model** opens the same guided setup as the
[first run](first-steps.md#1-set-up-your-ai): pick a provider, paste the key, list your models and test.

When a model is retired, Elissa switches to its replacement on her own.

## Voice

| Option | What it does | Default |
|---|---|---|
| **Voice** | Natural Edge voices for your language, plus offline system voices (Windows and macOS), marked *offline*. If the natural voice service fails, a system voice answers instead. | Salomé (es-CO) / Ava (en-US) |
| **Speed** | From 0.8× to 1.6×. | 1.10× |
| **Speech recognition** | How she understands you: *Automatic*, *Groq*, *OpenAI*, *On your PC* (Windows) or *Your own server*. See [Let her hear you](first-steps.md#2-let-her-hear-you). | Automatic |
| **API key for speech** | Shown when the chosen service needs a key. It's saved apart from your chat provider's key. | — |
| **Local model** | For *On your PC*: *Fast · 60 MB* or *More accurate · 190 MB*. Downloaded once. | Fast |
| **Transcription URL** | For *Your own server*: an OpenAI-compatible `/audio/transcriptions` URL. | — |
| **Wake her by saying…** | "Hola Elissa" / "Oye Elissa" with a Spanish voice; "Hey / Hi / Okay Elissa" with an English voice. Detected offline on your computer; downloads a 40 MB model the first time; pauses while the screen is locked. | Off |
| **Interrupt her by talking** | Talk over her answer to stop her. Best with headphones, so she doesn't hear herself. | Off |
| **While we talk, turn other apps down** | Lowers music and videos while you talk, to 10 %, 20 % or 35 %, or not at all. On macOS it lowers Spotify and Music. Not on Linux. | 20 % |
| **Continuous conversation** | After each answer she listens again. | On |
| **Always on top** | Keeps her above other windows. | On |
| **Start with the system** | Opens Elissa when you sign in. | — |
| **Shortcut to talk** | Click the field and press a combination. It must include ++ctrl++, ++alt++ or the Windows/Command key. | ++ctrl+alt+space++ |

## Sounds

| Option | What it does | Default |
|---|---|---|
| **Elissa's sounds** | Turns her sounds on or off. | On |
| **Volume** | Volume of her sounds (not of her voice). | 60 % |

To use your own sounds, choose **Open sounds folder** and drop a `.wav`, `.mp3`, `.ogg` or `.m4a` file named after the
sound you want to replace, then choose **Reload**. The names are: `greet`, `listen`, `stop`, `send`, `done`, `error`,
`approval`, `poke`, `annoyed`, `dizzy`, `love`, `happy`, `sleep`, `wake`, `open`, `close`, `drag` and `tick`. For
example, `listen.wav` or `done.mp3`.

## Email

| Option | What it does | Default |
|---|---|---|
| **Let her read my email** | Search and read email and save attachments, over IMAP. She never deletes email or marks it as read. | Off |
| **Let her send email** | Send over SMTP. Every email is shown to you on an approval card first. | Off |
| **Address** | Your email address. | — |
| **App password** | An app password, not your normal password. | — |
| **IMAP server** | Detected for Gmail, Outlook/Hotmail/Live, Yahoo and iCloud; otherwise `imap.<your domain>`. | Automatic |

Choose **Test and save email** to check the connection. For Gmail, turn on 2-step verification and create the
password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords). Attachments are saved to
`Downloads/Elissa adjuntos`.

## Integrations (MCP)

Connect Elissa to other services through [MCP](https://modelcontextprotocol.io) servers. Each server shows whether
it's connected and how many tools it has; you can turn it off or remove it.

**Add** offers:

| Integration | What you need |
|---|---|
| **GitHub** | A [GitHub personal access token](https://github.com/settings/personal-access-tokens). |
| **Jira and Confluence** | [Node.js](https://nodejs.org). The first time, your browser opens to sign in to Atlassian. |
| **Google Calendar** | Node.js and the path to your own Google Cloud OAuth credentials file (JSON). |
| **Other MCP server…** | A name, and either a remote URL (`https://`, or `http://127.0.0.1` / `localhost`) with an optional token, or a local command. |

Tools that only read run freely; anything that can change data asks for your approval first.

!!! warning
    Only add servers you trust: a local MCP server is a program that runs on your computer.

## Spotify

Elissa can play what you ask for on Spotify (Premium), on any of your devices. You use your own free Spotify app key:

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) and create an app.
2. In **Redirect URIs**, add `http://127.0.0.1/spotify/callback` and tick **Web API**.
3. Copy the app's **Client ID**, paste it in Elissa and choose **Connect Spotify**. Spotify opens so you can authorize.

The login lasts about six months; after that, connect again. Pause, next and "what's playing?" work without
connecting anything (on Windows and macOS).

## Claude Code and Codex alerts

*Windows and macOS.* Elissa tells you when a [Claude Code](https://claude.com/claude-code) or Codex session finishes,
fails, or needs your permission, with the project's name.

- **Install** adds a hook to the tool's settings (`~/.claude/settings.json` or `~/.codex/hooks.json`). It keeps what
  you already had and saves a copy next to it as `*.elissa-backup`. **Remove** takes it out.
- In Codex, approve the new hook once with `/hooks`.
- **Say alerts out loud**: without it you get a notification and a caption.

The hook only sends the kind of alert and the project folder's name, never your prompts or the answers, and it
always lets the session continue.

## Using the computer

*Windows.* **Let her see and use other windows** (on by default) lets her read the window you're working in, click,
type and press keys there. Every one of those actions asks for your approval. Password fields are never read.

## Folders she can use

The folders where she can find, read and write files. By default, your home folder. **Add folder** opens a folder
picker (on Linux it needs `zenity`).

Files you drop on her window can be read even if they're outside these folders.

## Memory

**New conversation** starts over. At the end of each conversation (or after 20 minutes without talking), Elissa
summarizes it and saves what matters as Markdown notes she can recall later.

The bottom of the panel shows your version, and **Update now** when a new one is ready.
