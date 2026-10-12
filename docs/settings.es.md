# Ajustes

Abre *Ajustes* con el engranaje de la ventana de Elissa o desde el menú de la bandeja (*Ajustes*). Es un solo panel
con una sección por tema, y los cambios se guardan a medida que los haces.

Las secciones que no aplican a tu sistema no aparecen.

## General

| Opción | Qué hace | Por defecto |
|---|---|---|
| **Idioma** | El idioma de la interfaz: *Automático (según el sistema)*, *Español* o *English*. Al cambiarlo también cambian el idioma y la voz con que habla. | Automático |
| **Nombre del asistente** | Cómo se llama ella (hasta 20 caracteres). | Elissa |
| **Tu nombre** | Para que te llame por tu nombre (hasta 30 caracteres). | — |

## Inteligencia artificial

Muestra el proveedor y el modelo en uso. **Cambiar proveedor o modelo** abre la misma configuración guiada de la
[primera vez](first-steps.md#1-configura-tu-ia): elige proveedor, pega la clave, lista tus modelos y prueba.

Cuando un modelo se retira, Elissa cambia sola a su reemplazo.

## Voz

| Opción | Qué hace | Por defecto |
|---|---|---|
| **Voz** | Voces naturales de Edge en tu idioma, más voces del sistema sin conexión (Windows y macOS), marcadas *sin conexión*. Si el servicio de voces naturales falla, responde una voz del sistema. | Salomé (es-CO) / Ava (en-US) |
| **Velocidad** | De 0,8× a 1,6×. | 1,10× |
| **Reconocimiento de voz** | Cómo te entiende: *Automático*, *Groq*, *OpenAI*, *En tu PC* (Windows) o *Servidor propio*. Mira [Que te escuche](first-steps.md#2-que-te-escuche). | Automático |
| **API key para la voz** | Aparece cuando el servicio elegido necesita clave. Se guarda aparte de la clave de tu proveedor de chat. | — |
| **Modelo local** | Para *En tu PC*: *Rápido · 60 MB* o *Más preciso · 190 MB*. Se descarga una vez. | Rápido |
| **URL de transcripción** | Para *Servidor propio*: una URL `/audio/transcriptions` compatible con OpenAI. | — |
| **Despertarla diciendo…** | «Hola Elissa» u «Oye Elissa» con una voz en español; «Hey / Hi / Okay Elissa» con una voz en inglés. Se detecta sin conexión en tu computador; descarga un modelo de 40 MB la primera vez; se pausa con la pantalla bloqueada. | Apagado |
| **Interrumpirla hablando** | Habla encima de su respuesta para pararla. Mejor con audífonos, para que no se oiga a sí misma. | Apagado |
| **Mientras hablamos, bajar las demás apps** | Baja la música y los videos mientras hablas: al 10 %, 20 % o 35 %, o no bajarlas. En macOS baja Spotify y Música. No está en Linux. | 20 % |
| **Conversación continua** | Después de cada respuesta vuelve a escuchar. | Activo |
| **Siempre visible** | La mantiene encima de las demás ventanas. | Activo |
| **Iniciar con el sistema** | Abre Elissa cuando inicias sesión. | — |
| **Atajo para hablar** | Haz clic en el campo y presiona una combinación. Debe incluir ++ctrl++, ++alt++ o la tecla Windows/Comando. | ++ctrl+alt+space++ |

## Sonidos

| Opción | Qué hace | Por defecto |
|---|---|---|
| **Sonidos de Elissa** | Activa o apaga sus sonidos. | Activo |
| **Volumen** | Volumen de sus sonidos (no de su voz). | 60 % |

Para usar tus propios sonidos, elige **Abrir carpeta de sonidos** y deja un archivo `.wav`, `.mp3`, `.ogg` o `.m4a`
con el nombre del sonido que quieres reemplazar; luego elige **Recargar**. Los nombres son: `greet`, `listen`, `stop`,
`send`, `done`, `error`, `approval`, `poke`, `annoyed`, `dizzy`, `love`, `happy`, `sleep`, `wake`, `open`, `close`,
`drag` y `tick`. Por ejemplo, `listen.wav` o `done.mp3`.

## Correo

| Opción | Qué hace | Por defecto |
|---|---|---|
| **Permitir que lea mi correo** | Buscar y leer correos y guardar adjuntos, por IMAP. Nunca borra correos ni los marca como leídos. | Apagado |
| **Permitir que envíe correos** | Enviar por SMTP. Cada correo se te muestra antes en una tarjeta de aprobación. | Apagado |
| **Dirección** | Tu correo. | — |
| **Contraseña de aplicación** | Una contraseña de aplicación, no tu contraseña normal. | — |
| **Servidor IMAP** | Se detecta para Gmail, Outlook/Hotmail/Live, Yahoo e iCloud; si no, `imap.<tu dominio>`. | Automático |

Elige **Probar y guardar correo** para revisar la conexión. Para Gmail, activa la verificación en dos pasos y crea la
contraseña en [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords). Los adjuntos se guardan
en `Descargas/Elissa adjuntos`.

## Integraciones (MCP)

Conecta a Elissa con otros servicios mediante servidores [MCP](https://modelcontextprotocol.io). Cada servidor muestra
si está conectado y cuántas herramientas tiene; puedes apagarlo o quitarlo.

**Agregar** ofrece:

| Integración | Qué necesitas |
|---|---|
| **GitHub** | Un [token personal de GitHub](https://github.com/settings/personal-access-tokens). |
| **Jira y Confluence** | [Node.js](https://nodejs.org). La primera vez se abre tu navegador para entrar a Atlassian. |
| **Google Calendar** | Node.js y la ruta de tu propio archivo de credenciales OAuth de Google Cloud (JSON). |
| **Otro servidor MCP…** | Un nombre y, o bien una URL remota (`https://`, o `http://127.0.0.1` / `localhost`) con un token opcional, o bien un comando local. |

Las herramientas que solo leen corren libres; todo lo que puede cambiar datos te pide aprobación antes.

!!! warning "Atención"
    Agrega solo servidores en los que confíes: un servidor MCP local es un programa que corre en tu computador.

## Spotify

Elissa puede poner lo que pidas en Spotify (Premium), en cualquiera de tus dispositivos. Usas tu propia clave gratis de
app de Spotify:

1. Entra a [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) y crea una app.
2. En **Redirect URIs** agrega `http://127.0.0.1/spotify/callback` y marca **Web API**.
3. Copia el **Client ID** de la app, pégalo en Elissa y elige **Conectar con Spotify**. Se abre Spotify para que
   autorices.

El inicio de sesión dura unos seis meses; después, conecta de nuevo. Pausar, siguiente y «¿qué suena?» funcionan sin
conectar nada (en Windows y macOS).

## Avisos de Claude Code y Codex

*Windows y macOS.* Elissa te avisa cuando una sesión de [Claude Code](https://claude.com/claude-code) o Codex termina,
falla o necesita tu permiso, con el nombre del proyecto.

- **Instalar** agrega un hook a la configuración de la herramienta (`~/.claude/settings.json` o
  `~/.codex/hooks.json`). Conserva lo que ya tenías y guarda una copia al lado como `*.elissa-backup`. **Quitar** lo
  saca.
- En Codex, aprueba el hook nuevo una vez con `/hooks`.
- **Decir los avisos en voz alta**: si no, recibes una notificación y un texto.

El hook solo envía el tipo de aviso y el nombre de la carpeta del proyecto, nunca lo que escribes ni las respuestas, y
siempre deja seguir la sesión.

## Uso del computador

*Windows.* **Permitir que vea y use otras ventanas** (activo por defecto) le deja leer la ventana en la que estás
trabajando, hacer clic, escribir y presionar teclas ahí. Cada una de esas acciones te pide aprobación. Nunca lee campos
de contraseña.

## Carpetas que puede usar

Las carpetas donde puede buscar, leer y escribir archivos. Por defecto, tu carpeta personal. **Agregar carpeta** abre
un selector de carpetas (en Linux necesita `zenity`).

Los archivos que sueltas sobre su ventana se pueden leer aunque estén fuera de estas carpetas.

## Memoria

**Nueva conversación** empieza de cero. Al terminar cada conversación (o tras 20 minutos sin hablar), Elissa la resume
y guarda lo importante en notas Markdown que puede recordar después.

Al final del panel aparece tu versión, y **Actualizar ahora** cuando hay una nueva lista.
