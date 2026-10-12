# Instalación

Descarga Elissa desde la [última versión](https://github.com/inginddie/elissa/releases/latest). Se publica una sola
versión para todos los sistemas, y las copias instaladas se actualizan solas.

=== ":fontawesome-brands-windows: Windows"

    **Requisitos:** Windows 10 (1809 o posterior) o Windows 11, de 64 bits, con WebView2 (viene en Windows 11),
    micrófono y parlantes.

    1. Descarga `Elissa_x.y.z_x64-setup.exe`.
    2. Ejecútalo. No necesita permisos de administrador: Elissa se instala solo para tu usuario.
    3. Elissa se abre en la esquina inferior derecha y te pide [configurar tu IA](first-steps.md#1-configura-tu-ia).

    !!! warning "Avisos de SmartScreen o Defender"
        El instalador todavía no está firmado, así que Windows SmartScreen puede advertirte la primera vez. Elige
        *Más información → Ejecutar de todas formas*.

        Si Microsoft Defender lo marca, es un falso positivo común en apps sin firmar hechas con PyInstaller.
        Actualiza Defender (`Update-MpSignature` en PowerShell) e inténtalo de nuevo, o
        [repórtalo](https://www.microsoft.com/wdsi/filesubmission). Cada versión la construye y autoprueba GitHub
        Actions desde el código público, y sus actualizaciones van firmadas. Mira la
        [política de firma de código](code-signing.md).

=== ":fontawesome-brands-apple: macOS"

    **Requisitos:** macOS 11 o posterior en Apple Silicon (M1 o más nuevo). Todavía no hay versión para Intel.

    1. Descarga `Elissa_x.y.z_aarch64.dmg`, ábrelo y arrastra Elissa a *Aplicaciones*.
    2. La app no está notarizada por Apple, así que la primera vez macOS no la abre. Ve a
       *Ajustes del Sistema → Privacidad y seguridad*, baja y elige **Abrir de todas formas**.
       O, en la Terminal:
       ```bash
       xattr -dr com.apple.quarantine /Applications/Elissa.app
       ```
    3. Permite el micrófono cuando lo pida. Después de una actualización macOS puede volver a preguntar; Elissa te
       dice dónde activarlo.
    4. La primera vez que controle Spotify o Música, macOS te pide permitir que Elissa controle esa app. Permítelo.

=== ":fontawesome-brands-linux: Linux"

    **Ubuntu, Debian y derivadas:** descarga `Elissa_x.y.z_amd64.deb` e instálalo:

    ```bash
    sudo apt install ./Elissa_x.y.z_amd64.deb
    ```

    **Cualquier otra distribución:** descarga el `.AppImage`, hazlo ejecutable y ábrelo. Necesita PortAudio para el
    micrófono (`libportaudio2` en sistemas basados en Debian):

    ```bash
    chmod +x Elissa_*.AppImage
    ./Elissa_*.AppImage
    ```

    Para agregar carpetas desde *Ajustes → Carpetas que puede usar*, instala `zenity`.

## Después de instalar

<figure class="shot small" markdown>
![Elissa descansando como un pequeño personaje en la esquina de la pantalla](media/screens/es/compact.png)
</figure>

Elissa aparece como un pequeño personaje en la esquina inferior derecha, y su ícono queda en la bandeja. Arrástrala a
donde quieras. Sigue con los [primeros pasos](first-steps.md).

## Qué funciona en cada sistema

Windows tiene todo. macOS y Linux son vistas previas: lo que no está disponible ahí se oculta o se explica en Ajustes.

| Función | Windows | macOS | Linux |
|---|:-:|:-:|:-:|
| Hablar con el atajo, chat, archivos, web, memoria, recordatorios, correo | :material-check: | :material-check: | :material-check: |
| Reconocimiento de voz en la nube (Groq, OpenAI, servidor propio) | :material-check: | :material-check: | :material-check: |
| Voces naturales (Edge) | :material-check: | :material-check: | :material-check: |
| Spotify (poner lo que pidas) e integraciones MCP | :material-check: | :material-check: | :material-check: |
| Palabra de activación «Hola Elissa» | :material-check: | :material-check: | sin probar |
| Abrir apps instaladas | :material-check: | :material-check: | — |
| «¿Qué suena?», pausar, siguiente | cualquier reproductor | Spotify y Música | solo con Spotify conectado |
| Bajar las demás apps mientras hablas | cualquier app | Spotify y Música | — |
| Volumen del sistema | :material-check: | :material-check: | — |
| Voces sin conexión | :material-check: | :material-check: | — |
| Comandos de terminal en tus proyectos | PowerShell | zsh | — |
| Avisos de Claude Code y Codex | :material-check: | :material-check: | — |
| Reconocimiento de voz en tu PC (whisper.cpp) | :material-check: | — | — |
| Usar otras ventanas (leer, clic, escribir) | :material-check: | — | — |

## Actualizaciones

Elissa busca una versión nueva 20 segundos después de abrir y cada 6 horas. Cuando hay una, el menú de la bandeja
muestra *Instalar la versión X* y *Ajustes* muestra **Actualizar ahora**. Las actualizaciones van firmadas y se
verifican antes de instalarse. También puedes buscarlas a mano desde la bandeja: *Buscar actualizaciones*.

## Desinstalar

- **Windows:** *Configuración → Aplicaciones → Aplicaciones instaladas → Elissa → Desinstalar*.
- **macOS:** cierra Elissa desde la bandeja y mueve la app de *Aplicaciones* a la Papelera.
- **Linux:** `sudo apt remove elissa`, o borra el AppImage.

Desinstalar no borra tus ajustes, memoria ni registros. Para quitarlos también, borra la
[carpeta de datos](faq.md#donde-estan-mis-datos) y quita las entradas *Elissa* del llavero de tu sistema.
