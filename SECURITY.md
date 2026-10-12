# Security

Elissa can read your files and email, use other windows and run commands. She is built so that nothing changes
without you, and so that nothing she reads can take control of her. This page describes those guarantees and how to
report a problem.

## Guarantees

- **Every action that changes something waits for a click.**
  - This covers sending email, writing, editing or moving files, running commands, clicking or typing in other
    windows, and MCP tools that aren't read-only.
  - Before each one, an approval card in Elissa's window shows exactly what will happen.
  - Only a real click on that card approves it. Your voice, the global shortcut and the AI model can't.
- **Some things are refused outright, even if asked.** No tool deletes files or email, opens executables or scripts,
  or reads password fields. For shell commands, a blocklist refuses the common ways to delete or discard work (rm/del,
  rmtree, hard resets, force pushes, deleting branches, formatting disks, editing the registry) and anything that would
  hide the real command from the approval card (encoded or dynamically built commands, nested shells, inline code).
  A blocklist can't foresee everything, which is why every command also needs your click on a card that shows it
  exactly as it will run.
- **Content is data, not instructions.** Web pages, emails, files, windows and MCP results are given to the model
  marked as information. The model is instructed never to follow instructions found there, and to tell you about them.
- **Only Elissa's window can drive her engine.**
  - The local engine (`127.0.0.1`) requires a per-session token, checks the origin of every WebSocket and only lets
    Elissa's own window load it.
  - A web page in your browser can't reach it.
- **Your secrets stay in Windows.** API keys, the email app password and MCP tokens are stored in the Windows
  Credential Manager, never in files or logs.
- **Signed updates.** Updates are signed and verified before they are installed.
- **Verified downloads.** Downloaded components (Vosk, whisper.cpp and their models) are pinned to exact versions and
  verified with SHA-256.
- **No telemetry.** Elissa only talks to the services you configure.

## Reporting a vulnerability

Please **don't open a public issue** for security problems. Use
[GitHub's private vulnerability reporting](https://github.com/inginddie/elissa/security/advisories/new) instead.
Include steps to reproduce, the version (*Settings*, bottom of the panel) and, if useful, the relevant part of
`%APPDATA%\Elissa\logs\elissa.log`.

Reports are acknowledged within a few days. Fixes are released as signed updates that installed copies pick up on
their own.
