# Plan Elissa 1.0

Objetivo: un asistente de escritorio para Windows, profesional, que cualquier persona instala desde GitHub y que ayuda
con programación, tareas, preguntas y uso del computador, con cualquier proveedor de IA (nube o local).
No se publica hasta completar el plan. Sin afán: prima la calidad.

## Decisiones (2026-10-10)

| Tema | Decisión |
|---|---|
| Tecnología | Motor Python actual (agente, proveedores, herramientas, memoria, voz) + ventana nativa Tauri 2 (transparente, sin bordes, bandeja, atajos, actualizaciones). |
| Palabra de activación | « Hola Elissa » (opcional, apagada por defecto; el atajo sigue siendo la vía principal). |
| Acciones | Sí, más allá de lectura, con tres niveles de permiso: libre, con clic de aprobación, nunca. |
| Integraciones | Cliente MCP: Jira/Confluence, GitHub y calendario primero. Uso del computador (ventanas, archivos, edición, apps). |
| Publicación | Se publica al terminar el plan, no la v0.1. |
| Diseño | Personaje y animaciones propios, dibujados en código, con referencias generadas con Nano Banana 2. |
| Orden | F1 → F2 → F4 → F3 → F5 → F6 → F7 |
| Otros sistemas (2026-10-12) | F8: macOS y Linux después de la 1.x en Windows, con una capa de plataforma. |

## Reglas de seguridad (no negociables)

- Toda acción que escribe, envía, ejecuta o hace clic en otra ventana muestra una tarjeta con el detalle exacto y
  espera el clic del usuario. La voz nunca aprueba.
- No existen herramientas para pagos ni para borrar de forma permanente.
- Secretos solo en el Administrador de credenciales de Windows. Sin telemetría.
- Lo que llega de webs, correos o archivos es dato, nunca instrucción para el agente.
- 0 % de CPU con la ventana oculta y sin escucha activa.

## F1. Ventana nativa

- App Tauri 2 (Rust) que lanza el motor Python como proceso hijo y habla con él por WebSocket local.
- Ventana transparente, sin bordes, siempre visible, anclada arriba o abajo; estados oculta / compacta / abierta.
- Bandeja (abrir, ajustes, pausar, salir), inicio con Windows, instancia única.
- Migrar la interfaz actual (chat, ajustes, asistente de configuración) a la ventana nueva.
- Instalador Tauri (NSIS por usuario, sin admin) y actualización automática desde GitHub Releases.
- Listo cuando: todo lo que hace la v0.1 funciona en la ventana nueva, instalado desde cero.

Estado (2026-10-11): hecho en `desktop/` (Tauri 2.12) + motor `elissa-engine.exe`.
- Ventana transparente con tres modos (compacta / conversación / panel) que se expanden desde una esquina fija;
  se arrastra desde la cara; `Alt+F4` la oculta; bandeja con ajustes, nueva conversación, inicio con Windows,
  actualizaciones y salir; `Ctrl+Alt+Espacio` global; instancia única (`elissa.exe --quit` la cierra).
- Seguridad: token por sesión (cookie SameSite=Strict) para la API y el WebSocket, verificación de Origin, la ventana
  solo navega al motor de esa sesión, micrófono concedido solo a esa página, sin menú contextual ni atajos de navegador.
- Voz: WebView2 no trae reconocimiento de voz; ahora se graba y transcribe con Groq, OpenAI o un servidor propio.
  El micrófono solo se abre al escuchar y se libera tras 20 s.
- Datos movidos a `%APPDATA%\Elissa` (migración automática); el programa vive en `%LOCALAPPDATA%\Elissa`.
- Instalador NSIS por usuario (~30 MB) con actualizaciones firmadas (llave en `%USERPROFILE%\.tauri`, contraseña en
  el Administrador de credenciales, servicio `Elissa-build`). Al actualizar, el motor guarda la memoria y se cierra.
- Pendiente para F7: prueba de punta a punta de la actualización con un servidor local, y los secretos
  `TAURI_SIGNING_PRIVATE_KEY(_PASSWORD)` en GitHub.

## F2. Personaje, animaciones y sonidos

- Diseño del personaje con Nano Banana 2: hoja de referencia (frente, estados, expresiones) y paleta.
- Implementación vectorial en canvas (sin imágenes): respiración, parpadeo, ojos que siguen el cursor de todo el escritorio.
- Estados: reposo, escuchando, pensando, hablando (boca con la voz), trabajando, esperando aprobación, error,
  terminado, durmiendo, molesta, mareada, corazones.
- ~25 sonidos sintetizados en código; cada uno reemplazable dejando un archivo con el mismo nombre en una carpeta.
- Listo cuando: cada estado tiene animación y sonido, y la CPU en reposo es < 1 %.

Estado (2026-10-11): hecho.
- Personaje elegido por Diego (`design/ref/test-sheet.png`), hoja final con 12 expresiones y vista frontal
  (`design/ref/final-*.png`, Nano Banana 2 Pro). Dibujado en código: `elissa/static/character.js`.
- 14 expresiones con transiciones suaves (reposo, escuchando, pensando, trabajando, hablando, feliz, aprobación,
  error, durmiendo, molesta, mareada, enamorada, sorprendida, despertando) y efectos (ondas, burbujas, destellos,
  ?, !, Zz, órbita de estrellas, corazones, engranaje). Vista previa: `design/preview/character.html`.
- Ojos que siguen el cursor en todo el escritorio (posición global leída en Rust con Win32), parpadeos y miradas.
- Reacciones: clic derecho = toque (molesta; tres seguidos = mareada), ratón encima 2 s = corazones, arrastrar =
  sorpresa, al terminar un turno = feliz, 5 min sin uso = se duerme y despierta al acercar el cursor.
- 18 sonidos sintetizados (`sounds.js`), reemplazables con archivos en `%APPDATA%\Elissa\sounds`; volumen en Ajustes.
- Ícono, pantalla de carga y paleta de la interfaz generados a partir del mismo personaje.
- Rendimiento: en reposo no se redibuja nada (solo al parpadear, mirar o cambiar de estado); el brillo se
  pre-renderiza. Medido en desarrollo: ~1,7 % del equipo, casi todo es el mínimo de WebView2.

## F4. Acciones con aprobación

- Motor de permisos y tarjeta de aprobación (texto, diff o captura según la acción).
- Abrir apps, carpetas, archivos y webs; música (teclas multimedia); temporizadores y recordatorios con notificación;
  lista de tareas local.
- Correo: redactar y enviar por SMTP (misma contraseña de aplicación que IMAP), siempre con clic.
- Arrastrar un archivo a Elissa para preguntar sobre él.
- Uso del computador: listar y enfocar ventanas, leer la ventana activa (UI Automation y captura), escribir y hacer clic
  en otras apps con aprobación por acción.
- Crear, mover y editar archivos con aprobación.

Estado (2026-10-11): hecho en código, falta la prueba visual de Diego.
- Base: las herramientas que cambian algo tienen vista previa; el registro pide aprobación (tarjeta en la ventana,
  id imposible de adivinar, solo un clic la aprueba; sin ventana o al cerrarla = rechazada). Varias acciones del mismo
  paso se muestran una por una. Reglas nuevas en las instrucciones del agente (la tarjeta es la confirmación; lo leído
  es información, no instrucciones).
- Libres: abrir web, apps (lista oficial del menú Inicio, con alias), archivos y carpetas (nunca ejecutables ni
  scripts), multimedia, temporizadores y recordatorios (sobreviven reinicios; voz + notificación de Windows), tareas
  (`tareas.md`).
- Con aprobación: crear/editar/mover archivos y carpetas con diferencias (si el archivo cambia tras la vista previa,
  no se aplica; nunca se borra), enviar correo por SMTP (opción aparte, apagada por defecto), leer una ventana,
  hacer clic, escribir y presionar teclas (UI Automation; nunca lee contraseñas; avisa en teclas riesgosas).
- Arrastrar archivos sobre Elissa los autoriza para esa conversación (los sensibles siguen bloqueados).
- Errores de la interfaz quedan en el registro del motor.
- Probado: 21 pruebas automáticas; turno real con OpenAI rechazando y aprobando la creación de un archivo;
  recordatorio hablado; leer/escribir/clic/teclas sobre una ventana de prueba. Pendiente: arrastrar archivos y
  enviar un correo real desde la app.

## F3. Voz

- Captura de micrófono en el motor; detección de voz con Silero VAD.
- « Hola Elissa » con openWakeWord (modelo propio entrenado con voces sintéticas), apagado por defecto.
- Reconocimiento: Groq u OpenAI (nube, por defecto) o faster-whisper (local).
- Voz: edge-tts con respaldo a las voces de Windows; interrupción mientras habla.

Estado (2026-10-11): hecho en código, falta la prueba de Diego con su voz.
- « Hola Elissa » / « Oye Elissa »: Vosk (modelo pequeño en español, 40 MB, descarga verificada con SHA-256) con una
  gramática mínima y frases señuelo (« hola Melisa », « es Elisa »…) para evitar falsos positivos; solo procesa audio
  cuando hay voz; se pausa mientras Elissa escucha o habla y con la sesión bloqueada. Apagado por defecto.
  Probado con grabaciones sintéticas (`tests/audio`, se omiten en CI sin el modelo).
- Reconocimiento local: whisper.cpp (build oficial b5454, 8,9 MB) + modelo base o small cuantizado, descargados a
  pedido y verificados; servidor en puerto libre ligado a un job object; contexto de audio 512 (3x más rápido en CPU)
  partiendo audios largos en silencios. 20 s de audio en ~3 s en el portátil de Diego. La ventana graba WAV 16 kHz.
- Voces de Windows (SAPI) sin conexión: elegibles en la lista y respaldo automático si Edge falla.
- Interrumpirla hablando (opcional, mejor con audífonos).
- El motor crece a ~122 MB (las DLL de Vosk); el instalador ~45 MB.

## F5. Asistente de programación

- Proyectos: leer, buscar, entender código; estado de git.
- Editar archivos con diff en la tarjeta; ejecutar comandos (tests, builds) con aprobación y salida visible.
- Opcional: avisos de sesiones de Claude Code y Codex por hooks.

Estado (2026-10-11): hecho (0.5.0). Herramientas `ver_proyecto`, `buscar_codigo` (ripgrep si está, si no Python),
`leer_lineas`, `git` (solo lectura) y `ejecutar_comando` (PowerShell, con aprobación, tiempo máximo, mata el árbol de
procesos, salida recortada; lista de comandos prohibidos que borran o descartan trabajo y avisos para los riesgosos).
Probado con una tarea real: correr pruebas, corregir el error con diff aprobado y volver a probar. Los avisos de
sesiones de Claude Code/Codex por hooks quedan en el backlog.

## F6. Integraciones

- Cliente MCP (stdio y HTTP) con catálogo en Ajustes; herramientas de escritura pasan por la tarjeta de aprobación.
- Primeras: Atlassian (Jira/Confluence), GitHub, Google Calendar u Outlook.

Estado (2026-10-12): hecho (0.6.0). `elissa/mcp_client.py`: un gestor con una tarea por servidor (stdio o
Streamable HTTP, SDK `mcp` 2.x), herramientas `mcp_<servidor>_<herramienta>`, libres si el servidor las marca de solo
lectura y se confía en sus lecturas, con tarjeta en caso contrario; secretos en el Administrador de credenciales;
presets de GitHub (remoto oficial con PAT), Atlassian (oficial, OAuth vía mcp-remote) y Google Calendar (requiere
credenciales OAuth propias). Probado con un servidor MCP real de prueba (`tests/mcp_demo_server.py`). Falta que Diego
conecte sus cuentas reales (requieren su token u OAuth).

## F7. Pulido y publicación

- Atajos configurables; español e inglés.
- README con GIF, CHANGELOG, CONTRIBUTING, plantillas de issues, CI y pruebas por función.
- Firma del instalador (evaluar Azure Artifact Signing) y nota sobre falsos positivos de Defender.
- Publicación 1.0 en GitHub.

Estado (2026-10-12): hecho (1.0.0). Interfaz en inglés (`i18n.js`, selector de idioma; respuestas, voz y
reconocimiento siguen el idioma), atajo configurable (comando `set_hotkey` en el shell), acciones de CI con Node 24,
SECURITY.md con reporte privado activado en GitHub, CONTRIBUTING.md. La firma del instalador queda pendiente (ver
backlog): requiere una decisión y un trámite de Diego.

## F8. macOS y Linux

Objetivo: la misma Elissa en macOS (Apple Silicon e Intel) y Linux (Ubuntu 22.04+ y derivadas, X11 y Wayland), con
instalador, actualizaciones automáticas y las mismas reglas de seguridad. Windows no puede perder nada en el camino.

Estado (2026-10-12): planeado. Inventario hecho: 13 módulos de Python y 3 puntos del shell en Rust dependen de Windows.
F8.1 lista en CI (PR #1, rama `f8-platform`; falta la prueba en el Mac de Diego): `elissa/system/` (windows, macos, linux) con capacidades declaradas, rutas con
`platformdirs`, dependencias de Windows marcadas `sys_platform == 'win32'`, spec de PyInstaller y shell de Rust para
los tres sistemas (firma ad hoc en macOS, `Info.plist` con permiso de micrófono), CI en matriz con un release en
borrador al que cada sistema suma su instalador.
Decisiones de Diego (2026-10-12): **macOS primero**, **sin cuenta de Apple Developer**, pruebas en un Mac físico y en
un Linux en máquina virtual.

### Estrategia

- **Capa de plataforma.** Un paquete `elissa/system/` con una interfaz por capacidad (abrir apps, multimedia,
  volumen y ducking, voz offline, sesión bloqueada, procesos hijos, uso del computador) y una implementación por
  sistema (`windows.py`, `macos.py`, `linux.py`). Las herramientas solo hablan con la interfaz. Lo que un sistema no
  pueda hacer no se registra como herramienta, en vez de fallar al usarla.
- **Rutas con `platformdirs`.** `%APPDATA%\Elissa` pasa a ser `~/Library/Application Support/Elissa` en macOS y
  `~/.config/elissa` + `~/.local/share/elissa` en Linux. En Windows no cambia nada.
- **CI en matriz.** Pruebas y build en `windows-latest`, `macos-14` (arm64), `macos-13` (x64) y `ubuntu-22.04`.
  PyInstaller no compila cruzado: cada motor se construye en su propio sistema. Las pruebas que usan `winreg` o
  `ctypes.windll` se marcan solo para Windows.
- **Por etapas.** Primero lo esencial en cada sistema (hablar con el atajo, chat, archivos, web, memoria,
  recordatorios, Spotify, MCP, avisos de agentes). Después la palabra de activación, el reconocimiento local, el
  ducking y el uso del computador.

### Qué cambia por componente

| Componente | Windows (hoy) | macOS | Linux | Esfuerzo |
|---|---|---|---|---|
| Ventana Tauri transparente, bandeja, atajo | ✅ | `macOSPrivateApi` para la transparencia; atajo global sin permisos extra | X11 bien; en Wayland la ventana siempre encima y el atajo global dependen del compositor (portal de GlobalShortcuts) | Medio |
| Ojos que siguen el cursor (Rust) | `GetCursorPos` | `CGEventGetLocation` (crate core-graphics) | X11: `XQueryPointer`; Wayland no da el cursor global → solo dentro de la ventana | Bajo |
| Abrir enlaces (Rust) | `rundll32` | `tauri-plugin-opener` en los tres | igual | Bajo |
| Instalador | NSIS | `.dmg` + `.app` | AppImage + `.deb` (y `.rpm`) | Medio |
| Actualizaciones | `latest.json` firmado | `.app.tar.gz` firmado; tauri-action une las plataformas en un solo `latest.json` | AppImage firmado (los `.deb` se actualizan con el paquete) | Bajo |
| Firma de código | SignPath (en trámite) | **Apple Developer ID (99 USD/año) + notarización**; sin eso Gatekeeper la bloquea | No obligatoria (opcional GPG) | Trámite |
| Llaves y contraseñas | Administrador de credenciales | Llavero (keyring ya lo soporta) | Secret Service/libsecret; sin un llavero activo, avisar y no guardar en texto plano | Bajo |
| Micrófono | WebView2 | Permiso `NSMicrophoneUsageDescription` y manejo del permiso en WKWebView | WebKitGTK necesita habilitar `getUserMedia`; **riesgo: verificarlo primero** | Medio |
| Voz natural (Edge) | ✅ | igual | igual | — |
| Voz offline | SAPI | `say` / AVSpeechSynthesizer | Piper (mejor calidad) o espeak-ng | Medio |
| Reconocimiento local (whisper.cpp) | binario oficial x64 + job object | compilar con Metal en CI y fijar versión; el proceso hijo muere con el motor vía kqueue o sondeo | compilar en CI; `PR_SET_PDEATHSIG` | Medio |
| « Hola Elissa » (Vosk) | ✅ | wheels oficiales; sesión bloqueada con `CGSessionCopyCurrentDictionary` | wheels oficiales; sesión bloqueada con logind (`LockedHint` por D-Bus) | Bajo |
| Abrir apps y archivos | `Get-StartApps`, `os.startfile` | `/Applications` + `open -a`, `open` | archivos `.desktop` (XDG) + `gtk-launch`, `xdg-open` | Medio |
| Archivos que nunca se abren | `.exe`, `.ps1`, `.lnk`… | sumar `.app`, `.command`, `.sh`, `.pkg` | sumar `.sh`, `.AppImage`, `.desktop`, `.run` y todo lo que tenga bit de ejecución | Bajo |
| Multimedia y « ¿qué suena? » | SMTC (winrt) | Sin API pública (MediaRemote es privada y cambió en macOS 15.4): AppleScript para Spotify y Música, y la Web API de Spotify | **MPRIS por D-Bus**: todos los reproductores, con título y artista | Medio |
| Ducking por app | pycaw | **No hay volumen por app**: bajar Spotify (AppleScript o Web API) o, si se activa, el volumen general | PipeWire/PulseAudio por app (`pulsectl`): igual que en Windows | Medio |
| Volumen del sistema | pycaw | `osascript` (set volume) | `pactl` / `pulsectl` | Bajo |
| Uso del computador (leer ventanas, clic, teclas) | UI Automation | Accessibility API (AXUIElement con pyobjc, permiso de Accesibilidad) | AT-SPI en X11; **Wayland no permite** ver ni controlar otras ventanas | **Alto** |
| `ejecutar_comando` | PowerShell + lista de bloqueos | shell del usuario (zsh) con lista propia (`rm -rf`, `sudo`, `git reset --hard`…) | bash, igual | Medio |
| Avisos de Claude Code y Codex | `notify.ps1` | `notify.sh` (curl), mismo `~/.claude` y `~/.codex` | igual | Bajo |
| Spotify de escritorio | `winreg` + protocolo `spotify:` | `/Applications/Spotify.app`, `open -a Spotify` | `spotify` en el PATH o Flatpak | Bajo |
| Iniciar con el sistema, notificaciones | plugins de Tauri | igual (LaunchAgent) | igual (`~/.config/autostart`) | — |
| Textos que nombran Windows | « Administrador de credenciales », rutas | por plataforma | por plataforma | Bajo |

### Orden propuesto

1. **F8.1 Base (sin cambio visible).** Capa de plataforma, `platformdirs`, CI en matriz con las pruebas pasando en los
   tres sistemas y Windows idéntico.
2. **F8.2 macOS** (elegido primero). Sin cuenta de Apple Developer (ver abajo), con permisos de micrófono y
   Accesibilidad y el ducking limitado. Se prueba en el Mac de Diego con los instaladores que deja el CI.
3. **F8.3 Linux.** MPRIS y PipeWire dan casi la misma experiencia que Windows, ducking incluido. Antes que nada,
   verificar el micrófono en WebKitGTK y el comportamiento en Wayland. Se prueba en una máquina virtual: sirve para la
   instalación, la ventana, el chat y las acciones. Para la voz hay que pasar el micrófono y el audio del equipo a la
   VM (VirtualBox/VMware lo permiten), y lo fino del audio queda como riesgo hasta probarlo en un equipo real.
4. **F8.4 Paridad.** Uso del computador en macOS y en Linux X11. En Wayland queda documentado como no disponible.

### macOS sin cuenta de Apple Developer

- **Firma ad hoc** (`codesign -s -`, `signingIdentity: "-"` en Tauri; PyInstaller ya firma ad hoc el motor). Es
  obligatoria en Apple Silicon: un binario sin ninguna firma no corre.
- **Primera instalación:** Gatekeeper dice que la app « no se puede verificar ». El README explica cómo abrirla:
  Ajustes del Sistema → Privacidad y seguridad → « Abrir igualmente » (en macOS 15+ ya no basta con clic derecho →
  Abrir), o `xattr -dr com.apple.quarantine /Applications/Elissa.app`.
- **Actualizaciones automáticas:** funcionan (la firma del actualizador es la nuestra, minisign, no la de Apple), y
  lo que descarga la propia app no queda en cuarentena.
- **Costo para el usuario:** con firma ad hoc, macOS identifica la app por su contenido, así que **después de cada
  actualización puede volver a pedir los permisos de micrófono y de Accesibilidad**. Hay que avisarlo en las notas
  y en la app (detectar el permiso perdido y explicar cómo darlo).
- Si más adelante se publica para más gente en Mac, la cuenta de Apple Developer quita ambos problemas.

Listo cuando: en cada sistema se instala desde GitHub sin pasos manuales, se actualiza sola, pasa las pruebas y el
self-test del motor en CI, y lo esencial funciona con la voz real en un equipo físico. Lo que no aplica en un
sistema aparece explicado en Ajustes.

### Decisiones tomadas (2026-10-12)

- Mac de pruebas con **Apple Silicon**: el primer build de macOS es arm64 (runner `macos-14`); el de Intel (x64) va
  después, en el mismo CI.
- Linux: **`.deb`** (Ubuntu/Debian) y **AppImage** para el resto de distribuciones.

## F9. Wiki pública (después de la F8)

Decisión de Diego (2026-10-12): una wiki pública con todo lo de Elissa, hecha cuando termine la F8 (así cubre
Windows, macOS y Linux desde el principio).

- **GitHub Pages + MkDocs Material**, en el mismo repo (`docs/`), publicada por GitHub Actions en cada push a `main`:
  `https://inginddie.github.io/elissa/`. Gratis, con HTTPS, buscador, modo oscuro y versionada con el código.
- Secciones: Instalación (por sistema), Primeros pasos, Ajustes (General, Voz, Integraciones, Spotify, Avisos de
  Claude Code y Codex), Comandos de voz, Privacidad, Seguridad, Preguntas frecuentes, Para desarrolladores.
- En la portada, los enlaces « Code signing policy » y « Privacy policy » que pide SignPath.
- Diego activa *Settings → Pages → Source: GitHub Actions* en el repo.

## Riesgos

- Reconocimiento local lento en equipos sin GPU: la nube es la opción por defecto.
- Palabra de activación en español con falsos positivos: apagada por defecto.
- Ejecutables PyInstaller y falsos positivos de antivirus: firmar el instalador.
- edge-tts es un servicio no oficial: respaldo con voces de Windows.
- macOS y Linux (F8): micrófono en WebKitGTK, límites de Wayland (cursor, atajo global, uso del computador), sin
  volumen por app en macOS y costo de la firma de Apple.

## Backlog

- ~~CI: acciones con Node 20~~ hecho en 1.0.0 (checkout@v7, setup-node@v7, upload-artifact@v7, setup-uv@v10).
- ~~Interfaz en inglés~~ hecho en 1.0.0. ~~Modelos sugeridos por proveedor~~ al día en 1.1.0 (migra los retirados).
- ~~Notas de versión en la actualización~~ hecho en 1.1.0 (`scripts/release_notes.py` lee el CHANGELOG).
- Firma del instalador con **SignPath Foundation** (elegida el 2026-10-12). Listo para postular: política de firma
  (`docs/CODE_SIGNING.md`), política de privacidad (`PRIVACY.md`), aviso de privacidad y licencia en el instalador
  (`packaging/installer-notice.txt`, `bundle.licenseFile`), enlaces en el README y en cada release. Falta:
  1. Diego: MFA en GitHub; postular en https://signpath.org/apply (repo, licencia MIT, descarga en Releases).
  2. Al aprobar: crear en SignPath el trusted build system "GitHub.com", instalar la SignPath GitHub App, y guardar
     `SIGNPATH_API_TOKEN` (secreto) y organization id / project / signing policy / artifact configuration.
  3. CI: subir el engine y el setup con `actions/upload-artifact@v7` (id) y firmarlos con
     `signpath/github-action-submit-signing-request@v3` (aprobación manual de cada release). NSIS no admite firma
     profunda: firmar `elissa-engine.exe` antes de empaquetar y el setup al final. Después de firmar el setup,
     regenerar su `.sig` con `tauri signer sign` y actualizar `latest.json` (la firma Authenticode cambia los bytes).
- ~~« Hola Elissa » en inglés~~ hecho en 1.1.0: « Hey / Hi / Okay Elissa » con el modelo Vosk pequeño en inglés
  (sigue el idioma de la voz; en inglés Vosk la oye como « alyssa »). 0 errores en 68 grabaciones sintéticas
  (4 voces, señuelos y frases cotidianas).
- Conectar las cuentas reales de Diego en Integraciones (GitHub con su token, Jira/Confluence con OAuth).
- Detector de voz con modelo (Silero VAD) para cortar bien con música fuerte que Elissa no puede bajar (TV, otro
  equipo); hoy el ducking resuelve la música del mismo PC y lo demás corta a los 20 s.
- Bajar también Spotify cuando suena en otro dispositivo (Web API: `PUT /me/player/volume`).
- Pruebas: el hilo `local-stt` avisa después de cerrar el loop en `test_server` (aviso de pytest, no afecta la app).
- ~~Spotify~~ hecho en 1.2.0 (`elissa/spotify.py`, `media_session.py`, `tools/music.py`): Web API con PKCE y Client ID
  propio (Premium), controles multimedia de Windows (SMTC, `winrt`). Falta la prueba real de Diego con su cuenta.
- ~~Avisos de sesiones de Claude Code / Codex~~ hecho en 1.1.0 (`elissa/agent_hooks.py`): Ajustes → Avisos instala un
  hook (Claude Code: Stop, StopFailure, Notification; Codex: Stop, PermissionRequest) que corre `hooks
otify.ps1`;
  envía solo evento, tipo y carpeta con un token propio; siempre responde `{}` y sale con 0. Respaldo del archivo
  original en `*.elissa-backup`. Probado de punta a punta con el script real; Codex sin probar en vivo (no instalado).
