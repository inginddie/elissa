# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versiones con [SemVer](https://semver.org/lang/es/).

## [1.6.0] - 2026-10-12

### Añadido (Linux)
- Música: « ¿qué suena? », pausar, reanudar, siguiente y anterior con cualquier reproductor que hable MPRIS
  (Spotify, Firefox, Chrome, VLC, Rhythmbox…).
- Mientras te escucha y responde, las demás apps bajan de volumen y vuelven al terminar (PulseAudio o PipeWire,
  con `pactl`). Volumen del sistema por voz.
- Voces sin internet con espeak-ng (si está instalado).
- Abrir apps instaladas (también Flatpak y Snap).
- Los ojos siguen el cursor en sesiones X11; « Hola Elissa » se pausa con la pantalla bloqueada (logind).
- Comandos de terminal en los proyectos (bash) y avisos de Claude Code y Codex.

### Corregido (Linux)
- La ventana no podía usar el micrófono: WebKitGTK lo trae apagado. Ahora se activa y se concede solo a Elissa.

## [1.5.0] - 2026-10-12

### Añadido (macOS)
- Los ojos de Elissa siguen el cursor por todo el escritorio.
- Música: « ¿qué suena? », pausar, reanudar, siguiente y anterior con Spotify y Música (la primera vez macOS pide
  permiso para que Elissa los controle).
- Mientras te escucha y responde, baja el volumen de Spotify y Música y lo devuelve al terminar (macOS no tiene
  volumen por app). Volumen del sistema por voz.
- Voces sin internet: las voces del sistema (`say`), también como respaldo si la voz de Edge falla.
- « Hola Elissa » se pausa con la pantalla bloqueada.
- Comandos de terminal en los proyectos (zsh), con tarjeta de aprobación y su propia lista de comandos prohibidos.
- Avisos de Claude Code y Codex.
- Si macOS quita el permiso de micrófono (puede pasar tras una actualización), Elissa dice cómo devolverlo.

### Cambiado
- Ajustes muestra solo lo que aplica en cada sistema y con sus nombres (Llavero de macOS, Credenciales de Windows).

## [1.4.0] - 2026-10-12

### Añadido
- Vista previa para **macOS** (Apple Silicon, `.dmg`) y **Linux** (`.deb` y AppImage), con actualizaciones
  automáticas. Funcionan: hablarle con el atajo o la voz (reconocimiento en la nube), chat, archivos, búsqueda web,
  memoria, recordatorios, Spotify, integraciones MCP y abrir apps (macOS). En macOS la app no está notarizada: la
  primera vez se abre desde Ajustes del Sistema → Privacidad y seguridad → « Abrir igualmente ».

### Cambiado
- Por dentro, todo lo que depende del sistema operativo pasa por una sola capa (Windows sigue igual).

## [1.3.0] - 2026-10-12

### Añadido
- Mientras Elissa te escucha y te responde, las demás apps que suenan (Spotify, YouTube, cualquier reproductor) bajan
  al 20 % sin pausarse, y vuelven a su volumen al terminar. Configurable en Ajustes → Voz (10, 20, 35 % o no bajarlas).
  Si moviste el volumen de una app mientras tanto, Elissa no lo toca; y siempre lo devuelve aunque se cierre.
- Terminar la conversación por voz: « listo », « gracias », « eso es todo », « chao »… y deja de esperar en el modo
  continuo. « Minimízate » o « escóndete » además la ocultan. Las frases cortas se reconocen al instante, sin la IA.
- Volumen del sistema por voz: « baja el volumen al 30 », « súbele un poco », « silencia ».

### Corregido
- Con música sonando, Elissa se quedaba « escuchando » hasta un minuto y enviaba la música al reconocimiento: ahora
  mide el ambiente después de bajar la música, aprende el nivel de tu voz y termina cuando dejas de hablar. El
  máximo por intervención baja de 60 s a 20 s.

## [1.2.0] - 2026-10-12

### Añadido
- Spotify: « pon Soda Stereo », « pon la canción X », « pon mi playlist de concentración ». Se conecta en Ajustes →
  Integraciones con tu propia app gratuita de Spotify (Client ID, sin contraseñas); reproducir necesita Premium. Si
  Spotify no está abierto, Elissa abre la app de escritorio o el reproductor web y espera a que aparezca. Funciona en
  cualquier dispositivo de tu cuenta, también el celular.
- « ¿Qué suena? »: Elissa dice la canción, el artista y el reproductor.

### Cambiado
- Pausar, reanudar, siguiente y anterior usan los controles multimedia de Windows y se dirigen a Spotify aunque haya
  otro reproductor abierto; si no hay ninguno, siguen funcionando las teclas multimedia.

## [1.1.0] - 2026-10-12

### Añadido
- « Hey Elissa » (o « Hi Elissa », « Okay Elissa ») para despertarla cuando su voz está en inglés; con la voz en
  español sigue siendo « Hola Elissa ». Cambia sola al cambiar el idioma y descarga el modelo en inglés (40 MB) la
  primera vez.
- Avisos de Claude Code y Codex: en Ajustes → Integraciones, un clic instala un hook para que Elissa te avise
  cuando una sesión termina, se detiene por un error o necesita tu permiso, con el nombre del proyecto. Por defecto
  muestra la notificación; decirlo en voz alta es opcional. No recibe lo que escribes ni las respuestas.

### Cambiado
- Modelos sugeridos al día: OpenAI `gpt-6-luna`, Anthropic `claude-haiku-5-5`, Gemini `gemini-3.5-flash-lite`,
  Groq `openai/gpt-oss-20b` y Ollama `qwen3:4b` (sin razonamiento, para responder rápido). El reconocimiento de voz
  con OpenAI usa `gpt-transcribe`.
- Si tenías un modelo que su proveedor apagó o va a apagar (`gpt-5-mini`, `llama-3.3-70b-versatile` en Groq), Elissa
  lo cambia sola por su reemplazo.
- La ventana de actualización muestra las novedades de cada versión.

## [1.0.0] - 2026-10-12

Primera versión completa del plan (F1–F7).

### Añadido
- Interfaz en inglés: Ajustes → General → Idioma (automático según Windows). Las respuestas, la voz y el
  reconocimiento siguen el idioma elegido.
- Atajo para hablar configurable (Ajustes → Voz); si otra app ya usa la combinación, Elissa lo avisa y conserva la
  anterior.
- Política de seguridad (SECURITY.md) con reporte privado de vulnerabilidades, y guía para contribuir.

### Cambiado
- Integración continua con las acciones de GitHub basadas en Node 24.

## [0.6.0] - 2026-10-12

### Añadido
- Integraciones por MCP: conecta servidores locales (programas) o remotos (URL) y Elissa usa sus herramientas.
  Ajustes trae listos GitHub, Jira y Confluence (servidor oficial de Atlassian) y Google Calendar, además de
  cualquier otro servidor. Lo que solo lee es libre; lo que cambia datos muestra la tarjeta de aprobación con el
  servidor, la herramienta y los datos exactos. Los tokens quedan en el Administrador de credenciales.

### Corregido
- La voz de Edge dejó de responder (403) porque Microsoft movió el servicio: ahora Elissa cambia sola al servidor
  nuevo, y si aun así falla usa la voz de Windows.

## [0.5.0] - 2026-10-11 (incluida en 0.6.0; su compilación no se publicó)

### Añadido
- Asistente de programación: ve la estructura de un proyecto, busca en el código, lee líneas numeradas y consulta git
  (estado, diferencias, historial) sin pedir permiso.
- Ejecuta comandos (pruebas, builds, lint, commits) con una tarjeta que muestra el comando exacto y la carpeta, y avisa
  si el comando publica, instala o escribe archivos.
- Con eso puede encargarse de "corre las pruebas, encuentra el error y corrígelo": edita con diferencias y vuelve a
  probar, pidiendo aprobación en cada paso.

### Seguridad
- Nunca ejecuta comandos que borran archivos o descartan trabajo (rm, del, reset duro de git, push forzado, borrar
  ramas, formatear…), aunque se los pidan.

## [0.4.0] - 2026-10-11

### Añadido
- « Hola Elissa » y « Oye Elissa » para despertarla sin tocar nada. Funciona sin internet: nada de lo que escucha sale
  de tu PC hasta que la despiertas. Se activa en Ajustes → Voz y se pausa con la pantalla bloqueada.
- Reconocimiento de voz en tu PC (whisper.cpp): privado, sin API key ni internet. Se descarga una sola vez, en versión
  rápida (60 MB) o más precisa (190 MB).
- Voces de Windows sin conexión, y respaldo automático si la voz de Edge no responde.
- Interrumpirla hablando mientras responde (opcional; mejor con audífonos).

### Corregido
- Elissa decía que el correo no estaba configurado aunque sí lo estaba: había guardado ese estado como recuerdo.
  La memoria ya no guarda estados del propio asistente, en cada turno sabe qué tiene activo de verdad y descarta
  recuerdos que copian la plantilla.

## [0.3.0] - 2026-10-11

### Añadido
- Elissa ya puede hacer cosas, siempre con una tarjeta de aprobación para lo que cambia algo:
  - Sin aprobación: abrir páginas, apps, archivos y carpetas; controlar la música y el volumen; temporizadores y
    recordatorios (con voz y notificación de Windows); lista de tareas.
  - Con aprobación: crear, editar y mover archivos (ves las diferencias antes), enviar correos (opción aparte en
    Ajustes) y usar otras ventanas: leerlas, hacer clic, escribir y presionar teclas.
- Arrastra un archivo sobre Elissa para preguntarle por él.

### Corregido
- Error 400 al hablarle justo después de una respuesta o al soltar un archivo: podían quedar dos grabaciones a la vez
  y el audio llegaba corrupto. Ahora hay una sola grabación por vez y el motor descarta audios vacíos o dañados con
  un mensaje claro.

### Seguridad
- Solo un clic en la tarjeta aprueba una acción; la voz, el atajo y el modelo no pueden. Sin ventana abierta, todo
  queda rechazado. Nunca se leen campos de contraseña ni se abren ejecutables.

## [0.2.0] - 2026-10-11

### Añadido
- Elissa tiene cuerpo: un personaje propio dibujado en código, con 14 expresiones, efectos y transiciones suaves.
  Sigue el cursor con la mirada en todo el escritorio, parpadea, reacciona si la tocas (clic derecho), si dejas el
  ratón encima o si la arrastras, celebra al terminar una respuesta y se duerme si no la usas.
- 18 sonidos propios, sintetizados; cada uno se puede reemplazar con un archivo y el volumen se ajusta en Ajustes.
- Ícono, pantalla de carga y colores nuevos a partir del personaje.
- Ventana nativa (Tauri): burbuja transparente que se expande al conversar y vuelve a encogerse, se arrastra
  desde la cara, vive en la bandeja del sistema y puede iniciar con Windows.
- Actualizaciones automáticas firmadas: Elissa avisa cuando hay una versión nueva y se actualiza con un clic.
- Reconocimiento de voz con Groq, OpenAI o un servidor Whisper propio, con su clave en Ajustes → Voz.
- `elissa.exe --quit` cierra la instancia en ejecución guardando la conversación.

### Cambiado
- Los datos (ajustes, memoria, registros) pasan a `%APPDATA%\Elissa`; se migran solos desde la versión anterior.
- El micrófono solo se abre mientras escucha y se libera a los 20 segundos.
- Instalador nuevo (NSIS por usuario, sin permisos de administrador).

### Seguridad
- El motor local solo acepta a la ventana de Elissa (token por sesión y verificación de origen).

### Corregido
- Títulos de conversación que copiaban la plantilla cuando el modelo local era pequeño.
- Escribir mientras escuchaba podía dejar la interfaz en reposo durante la respuesta.

## [0.1.0] - 2026-10-10

- Primera versión: asistente de voz con cualquier proveedor de IA, archivos, web, correo de solo lectura y memoria.
