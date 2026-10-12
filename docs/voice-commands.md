# Voice commands

You don't need exact phrases: talk to Elissa naturally, in Spanish or English, and she picks the right tool. These
examples show what she can do. Actions marked **:material-hand-back-right: approval** show a card and wait for your
click.

## Conversation

| Say | What happens |
|---|---|
| "Thanks, that's all", "bye", "I'm done", "listo, gracias", "chao" | Ends the conversation |
| "Hide", "go away", "minimízate", "escóndete" | Hides her window |
| "Hey Elissa, …" | Wakes her (if the [wake phrase](settings.md#voice) is on) |

The short phrases above work on their own, without the AI, as long as they're the whole sentence.

## Music and volume

| Say | Notes |
|---|---|
| "Play Daft Punk", "play my focus playlist", "pon Soda Stereo" | Needs [Spotify connected](settings.md#spotify) (Premium). Plays songs, artists, albums or your playlists, on any of your devices |
| "Pause", "next song", "skip 3 songs", "go back" | Windows: any player. macOS: Spotify and Music. Linux: Spotify connected |
| "What's playing?" | Same as above |
| "Turn the volume down to 30", "a little louder", "mute" | System volume. Windows and macOS |

## Apps, sites and files

| Say | Notes |
|---|---|
| "Open Excel", "open Spotify", "open the calculator" | Installed apps. Windows and macOS |
| "Open github.com" | Opens the site in your browser |
| "Open my Downloads folder", "show me that file in its folder" | Never opens programs or scripts |
| "Read the PDF I just downloaded", "what does this spreadsheet say?" | PDF, Word, Excel, CSV, text and code in your allowed folders |
| "Find the files about the budget", "search for 'invoice' in my documents" | Searches names and contents |
| "Write a summary to notes.md", "rename that file", "move it to Documents" | :material-hand-back-right: approval, with a diff. Nothing is ever deleted |

Drop a file on her window to ask about it.

## Timers, reminders and tasks

| Say | Notes |
|---|---|
| "5-minute timer" | Up to 24 hours |
| "Remind me at 3 pm to call Ana", "remind me in 20 minutes to stretch" | A reminder missed while she was closed arrives when she opens, with a note |
| "What reminders do I have?", "cancel the 3 pm reminder" | |
| "Add buy bread to my tasks", "what are my tasks?", "mark buy bread as done" | Saved in `tareas.md` in your data folder |

Reminders and timers show a system notification, and she says them out loud if she isn't busy.

## Web

| Say | Notes |
|---|---|
| "Search the web for…", "what's the latest on…" | DuckDuckGo, no extra key |
| "Read this page: …", "summarize this online PDF" | |

## Email

*Needs [Email](settings.md#email) turned on.*

| Say | Notes |
|---|---|
| "Do I have emails from Ana?", "read the last email from the bank" | Read-only |
| "Save the attachments from that email" | To `Downloads/Elissa adjuntos` |
| "Reply to Ana that I'll be there at 5" | :material-hand-back-right: approval, showing the full email. Needs *Let her send email* |

## Code

| Say | Notes |
|---|---|
| "What is this project?", "where is the login handled?" | Reads the project and searches the code |
| "What changed?", "show me the git log" | git status, diff, log and branches (read-only) |
| "Run the tests, find the bug and fix it" | Edits are :material-hand-back-right: approval with a diff; commands are :material-hand-back-right: approval. Windows (PowerShell) and macOS (zsh) |

Commands that delete or discard work (`rm`, `del`, hard resets, force pushes, deleting branches…) are refused, even
if you ask.

## Your computer

*Windows, with [Using the computer](settings.md#using-the-computer) on.*

| Say | Notes |
|---|---|
| "What is this?", "what does this window say?" | Reads the window you're working in |
| "Switch to Excel", "what windows are open?" | |
| "Click Save", "type my address", "press Ctrl+S" | :material-hand-back-right: approval |

Password fields are never read.

## Memory

| Say | Notes |
|---|---|
| "Remember that I prefer meetings in the morning" | Saved as a note |
| "What did we talk about yesterday?", "what did I tell you about the trip?" | Searches past conversations |

## Integrations

With [MCP servers](settings.md#integrations-mcp) connected, just ask: "what are my open GitHub issues?", "create a
Jira ticket for…", "what's on my calendar tomorrow?". Reading runs freely; anything that changes data shows a card.
