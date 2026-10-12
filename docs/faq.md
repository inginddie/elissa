# FAQ

## Where is my data?

Your settings, memory, reminders, tasks, sounds and logs are readable Markdown and JSON files in:

| System | Folder |
|---|---|
| Windows | `%APPDATA%\Elissa` |
| macOS | `~/Library/Application Support/Elissa` |
| Linux | `~/.local/share/Elissa` |

Your API keys, email password and integration tokens aren't there: they're in your system's keychain (Windows
Credential Manager, macOS Keychain or Linux Secret Service), under *Elissa*.

Uninstalling Elissa doesn't delete this folder.

## Questions

??? question "Is Elissa free?"

    Yes, Elissa is free and open source. The AI providers you connect may charge for their use; Ollama and LM Studio are
    free and run on your computer.

??? question "Can I use her without internet?"

    Yes, on Windows: pick Ollama or LM Studio as the AI, *On your PC* for speech recognition and a Windows voice. The wake
    phrase always works offline. Web search, email and integrations need internet, of course.

??? question "She doesn't hear me"

    - Check that *Settings → Voice → Speech recognition* says which service it's using. If it asks for a key, paste a
      Groq or OpenAI key there.
    - **macOS:** *System Settings → Privacy & Security → Microphone → Elissa* must be on. After an update macOS may turn
      it off again.
    - **Linux:** the microphone needs PortAudio (`libportaudio2`).
    - Make sure the right microphone is your system's default input.

??? question "The wake phrase doesn't work"

    - Turn it on in *Settings → Voice*. The status below it should say she's listening.
    - It pauses while she listens or speaks, and while your screen is locked.
    - It follows her voice's language: with a Spanish voice say "Hola Elissa" or "Oye Elissa"; with an English voice,
      "Hey Elissa", "Hi Elissa" or "Okay Elissa".

??? question "The shortcut doesn't work"

    Another app may be using it. Pick another one in *Settings → Voice → Shortcut to talk*. On Linux with Wayland, global
    shortcuts depend on your desktop environment.

??? question "Windows warns me about the installer"

    The installer isn't code-signed yet. See [Install → Windows](install.md).

??? question "macOS says Elissa can't be opened"

    The app isn't notarized by Apple. See [Install → macOS](install.md).

??? question "How do I quit her?"

    Closing her window only hides her. To quit, use the tray icon → *Salir*.

??? question "Why does she ask before doing things?"

    Because anything that changes something (sending, writing, moving, clicking, typing, running) needs your OK. Only a
    click on the card approves it, so nobody (not a web page, not an email, not the AI) can act in your name. See
    [Security](security.md).

??? question "How do I report a bug or ask for a feature?"

    Open an [issue on GitHub](https://github.com/inginddie/elissa/issues). Include your version (bottom of *Settings*)
    and, if useful, the relevant part of `logs/elissa.log` in your [data folder](#where-is-my-data). For security
    problems, see [Security](security.md#reporting-a-vulnerability).
