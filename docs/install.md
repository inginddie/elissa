# Install

Download Elissa from the [latest release](https://github.com/inginddie/elissa/releases/latest). One version is
published for every system, and installed copies update themselves.

=== ":fontawesome-brands-windows: Windows"

    **Requirements:** Windows 10 (1809 or later) or Windows 11, 64-bit, with WebView2 (built into Windows 11), a
    microphone and speakers.

    1. Download `Elissa_x.y.z_x64-setup.exe`.
    2. Run it. No administrator rights are needed; Elissa installs for your user only.
    3. Elissa opens in the bottom-right corner and asks you to [set up your AI](first-steps.md#1-set-up-your-ai).

    !!! warning "SmartScreen or Defender warnings"
        The installer isn't code-signed yet, so Windows SmartScreen may warn you the first time. Choose
        *More info → Run anyway*.

        If Microsoft Defender flags it, that's a false positive common with unsigned apps built with PyInstaller.
        Update Defender (`Update-MpSignature` in PowerShell) and try again, or
        [report it](https://www.microsoft.com/wdsi/filesubmission). Every release is built and self-tested by GitHub
        Actions from the public code, and its updates are signed. See the [code signing policy](code-signing.md).

=== ":fontawesome-brands-apple: macOS"

    **Requirements:** macOS 11 or later on Apple Silicon (M1 or newer). There is no Intel build yet.

    1. Download `Elissa_x.y.z_aarch64.dmg`, open it and drag Elissa to *Applications*.
    2. The app isn't notarized by Apple, so the first time macOS won't open it. Go to
       *System Settings → Privacy & Security*, scroll down and choose **Open Anyway**.
       Or, in Terminal:
       ```bash
       xattr -dr com.apple.quarantine /Applications/Elissa.app
       ```
    3. Allow the microphone when she asks. After an update macOS may ask again; Elissa tells you where to turn it
       back on.
    4. The first time she controls Spotify or Music, macOS asks you to let Elissa control that app. Allow it.

=== ":fontawesome-brands-linux: Linux"

    **Ubuntu, Debian and derivatives:** download `Elissa_x.y.z_amd64.deb` and install it:

    ```bash
    sudo apt install ./Elissa_x.y.z_amd64.deb
    ```

    **Any other distribution:** download the `.AppImage`, make it executable and run it. It needs PortAudio for the
    microphone (`libportaudio2` on Debian-based systems):

    ```bash
    chmod +x Elissa_*.AppImage
    ./Elissa_*.AppImage
    ```

    To add folders from *Settings → Folders she can use*, install `zenity`.

## What works on each system

Windows has everything. macOS and Linux are previews: what isn't available there is hidden or explained in Settings.

| Feature | Windows | macOS | Linux |
|---|:-:|:-:|:-:|
| Talk with the shortcut, chat, files, web, memory, reminders, email | :material-check: | :material-check: | :material-check: |
| Speech recognition in the cloud (Groq, OpenAI, your own server) | :material-check: | :material-check: | :material-check: |
| Natural voices (Edge) | :material-check: | :material-check: | :material-check: |
| Spotify (play what you ask for) and MCP integrations | :material-check: | :material-check: | :material-check: |
| "Hey Elissa" wake phrase | :material-check: | :material-check: | not tested |
| Open installed apps | :material-check: | :material-check: | — |
| "What's playing?", pause, skip | any player | Spotify and Music | only with Spotify connected |
| Turn other apps down while you talk | any app | Spotify and Music | — |
| System volume | :material-check: | :material-check: | — |
| Offline voices | :material-check: | :material-check: | — |
| Terminal commands in your projects | PowerShell | zsh | — |
| Claude Code and Codex alerts | :material-check: | :material-check: | — |
| Speech recognition on your computer (whisper.cpp) | :material-check: | — | — |
| Use other windows (read, click, type) | :material-check: | — | — |

## Updates

Elissa checks for a new version 20 seconds after starting and every 6 hours. When there is one, the tray menu shows
*Instalar la versión X* and *Settings* shows **Update now**. Updates are signed and verified before they are
installed. You can also check by hand from the tray: *Buscar actualizaciones*.

## Uninstall

- **Windows:** *Settings → Apps → Installed apps → Elissa → Uninstall*.
- **macOS:** quit Elissa from the tray and move it from *Applications* to the Trash.
- **Linux:** `sudo apt remove elissa`, or delete the AppImage.

Uninstalling doesn't delete your settings, memory and logs. To remove them too, delete the
[data folder](faq.md#where-is-my-data), and remove the *Elissa* entries from your system's keychain.
