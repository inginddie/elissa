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

## Riesgos

- Reconocimiento local lento en equipos sin GPU: la nube es la opción por defecto.
- Palabra de activación en español con falsos positivos: apagada por defecto.
- Ejecutables PyInstaller y falsos positivos de antivirus: firmar el instalador.
- edge-tts es un servicio no oficial: respaldo con voces de Windows.

## Backlog

- CI: actualizar las acciones que aún usan Node 20 (`actions/checkout@v4`, `actions/setup-node@v4`,
  `actions/upload-artifact@v4`, `astral-sh/setup-uv@v6`) a versiones con Node 24 antes de que GitHub retire Node 20
  (aviso visto en la primera compilación, 2026-10-11).
- Interfaz en inglés (F7) y revisar los modelos sugeridos por proveedor.
- Avisos de sesiones de Claude Code / Codex (hooks), como en Coucou.
