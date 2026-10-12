# Comandos de voz

No necesitas frases exactas: háblale a Elissa con naturalidad, en español o en inglés, y ella elige la herramienta
correcta. Estos ejemplos muestran lo que puede hacer. Las acciones marcadas con
**:material-hand-back-right: aprobación** muestran una tarjeta y esperan tu clic.

## Conversación

| Di | Qué pasa |
|---|---|
| «Listo, gracias», «eso es todo», «chao», «adiós», «ya está» | Termina la conversación |
| «Minimízate», «escóndete», «vete», «desaparece» | Esconde su ventana |
| «Hola Elissa, …» | La despierta (si la [frase de activación](settings.md#voz) está activa) |

Las frases cortas de arriba funcionan solas, sin la IA, siempre que sean la frase completa.

## Música y volumen

| Di | Notas |
|---|---|
| «Pon Soda Stereo», «pon mi playlist de concentración» | Necesita [Spotify conectado](settings.md#spotify) (Premium). Pone canciones, artistas, álbumes o tus playlists, en cualquiera de tus dispositivos |
| «Pausa», «siguiente canción», «salta 3 canciones», «la anterior» | Windows: cualquier reproductor. macOS: Spotify y Música. Linux: Spotify conectado |
| «¿Qué suena?» | Igual que arriba |
| «Baja el volumen al 30», «súbele un poco», «silencia» | Volumen del sistema. Windows y macOS |

## Apps, sitios y archivos

| Di | Notas |
|---|---|
| «Abre Excel», «abre Spotify», «abre la calculadora» | Apps instaladas. Windows y macOS |
| «Abre github.com» | Abre el sitio en tu navegador |
| «Abre mi carpeta de Descargas», «muéstrame ese archivo en su carpeta» | Nunca abre programas ni scripts |
| «Lee el PDF que acabo de descargar», «¿qué dice esta hoja de cálculo?» | PDF, Word, Excel, CSV, texto y código en tus carpetas permitidas |
| «Busca los archivos del presupuesto», «busca "factura" en mis documentos» | Busca en nombres y contenidos |
| «Escribe un resumen en notas.md», «renombra ese archivo», «muévelo a Documentos» | :material-hand-back-right: aprobación, con un diff. Nunca borra nada |

Suelta un archivo sobre su ventana para preguntarle por él.

## Temporizadores, recordatorios y tareas

| Di | Notas |
|---|---|
| «Temporizador de 5 minutos» | Hasta 24 horas |
| «Recuérdame a las 3 llamar a Ana», «recuérdame en 20 minutos estirarme» | Un recordatorio que se pasó mientras estaba cerrada llega cuando abre, con una nota |
| «¿Qué recordatorios tengo?», «cancela el recordatorio de las 3» | |
| «Agrega comprar pan a mis tareas», «¿cuáles son mis tareas?», «marca comprar pan como hecha» | Se guardan en `tareas.md` en tu carpeta de datos |

Los recordatorios y temporizadores muestran una notificación del sistema, y los dice en voz alta si no está ocupada.

## Web

| Di | Notas |
|---|---|
| «Busca en internet…», «¿qué hay de nuevo sobre…?» | DuckDuckGo, sin clave extra |
| «Lee esta página: …», «resume este PDF en línea» | |

## Correo

*Necesita [Correo](settings.md#correo) activo.*

| Di | Notas |
|---|---|
| «¿Tengo correos de Ana?», «lee el último correo del banco» | Solo lectura |
| «Guarda los adjuntos de ese correo» | En `Descargas/Elissa adjuntos` |
| «Respóndele a Ana que llego a las 5» | :material-hand-back-right: aprobación, con el correo completo. Necesita *Permitir que envíe correos* |

## Código

| Di | Notas |
|---|---|
| «¿Qué es este proyecto?», «¿dónde se maneja el login?» | Lee el proyecto y busca en el código |
| «¿Qué cambió?», «muéstrame el log de git» | git status, diff, log y ramas (solo lectura) |
| «Corre las pruebas, encuentra el error y arréglalo» | Las ediciones son :material-hand-back-right: aprobación con un diff; los comandos también. Windows (PowerShell) y macOS (zsh) |

Los comandos que borran o descartan trabajo (`rm`, `del`, resets duros, force push, borrar ramas…) se rechazan, aunque
se lo pidas.

## Tu computador

*Windows, con [Uso del computador](settings.md#uso-del-computador) activo.*

| Di | Notas |
|---|---|
| «¿Qué es esto?», «¿qué dice esta ventana?» | Lee la ventana en la que estás trabajando |
| «Cambia a Excel», «¿qué ventanas hay abiertas?» | |
| «Haz clic en Guardar», «escribe mi dirección», «presiona Ctrl+S» | :material-hand-back-right: aprobación |

Nunca lee campos de contraseña.

## Memoria

| Di | Notas |
|---|---|
| «Recuerda que prefiero las reuniones en la mañana» | Se guarda como nota |
| «¿De qué hablamos ayer?», «¿qué te dije del viaje?» | Busca en conversaciones pasadas |

## Integraciones

Con [servidores MCP](settings.md#integraciones-mcp) conectados, solo pide: «¿cuáles son mis issues abiertos en
GitHub?», «crea un ticket en Jira para…», «¿qué tengo mañana en el calendario?». Leer corre libre; todo lo que cambia
datos muestra una tarjeta.
