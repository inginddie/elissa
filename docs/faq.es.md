# Preguntas frecuentes

## ¿Elissa es gratis?

Sí, Elissa es gratis y de código abierto. Los proveedores de IA que conectes pueden cobrar por su uso; Ollama y LM
Studio son gratis y corren en tu computador.

## ¿Dónde están mis datos?

Tus ajustes, memoria, recordatorios, tareas, sonidos y registros son archivos Markdown y JSON legibles en:

| Sistema | Carpeta |
|---|---|
| Windows | `%APPDATA%\Elissa` |
| macOS | `~/Library/Application Support/Elissa` |
| Linux | `~/.local/share/Elissa` |

Tus API keys, la contraseña del correo y los tokens de integraciones no están ahí: están en el llavero de tu sistema
(Administrador de credenciales de Windows, Llavero de macOS o Secret Service de Linux), bajo *Elissa*.

Desinstalar Elissa no borra esta carpeta.

## ¿Puedo usarla sin internet?

Sí, en Windows: elige Ollama o LM Studio como IA, *En tu PC* para el reconocimiento de voz y una voz de Windows. La
frase de activación siempre funciona sin internet. La búsqueda web, el correo y las integraciones sí necesitan
internet.

## No me escucha

- Revisa que *Ajustes → Voz → Reconocimiento de voz* diga qué servicio está usando. Si pide una clave, pega ahí una de
  Groq u OpenAI.
- **macOS:** *Ajustes del Sistema → Privacidad y seguridad → Micrófono → Elissa* debe estar activo. Después de una
  actualización macOS puede apagarlo otra vez.
- **Linux:** el micrófono necesita PortAudio (`libportaudio2`).
- Asegúrate de que el micrófono correcto sea la entrada predeterminada de tu sistema.

## La frase de activación no funciona

- Actívala en *Ajustes → Voz*. El estado debajo debe decir que está escuchando.
- Se pausa mientras ella escucha o habla, y mientras la pantalla está bloqueada.
- Sigue el idioma de su voz: con una voz en español di «Hola Elissa» u «Oye Elissa»; con una voz en inglés, «Hey
  Elissa», «Hi Elissa» u «Okay Elissa».

## El atajo no funciona

Puede que otra app lo use. Elige otro en *Ajustes → Voz → Atajo para hablar*. En Linux con Wayland, los atajos
globales dependen de tu entorno de escritorio.

## Windows me advierte sobre el instalador

El instalador todavía no está firmado. Mira [Instalación → Windows](install.md).

## macOS dice que no puede abrir Elissa

La app no está notarizada por Apple. Mira [Instalación → macOS](install.md).

## ¿Cómo la cierro?

Cerrar su ventana solo la esconde. Para salir, usa el ícono de la bandeja → *Salir*.

## ¿Por qué pregunta antes de hacer cosas?

Porque todo lo que cambia algo (enviar, escribir, mover, hacer clic, escribir texto, ejecutar) necesita tu permiso.
Solo un clic en la tarjeta lo aprueba, así que nadie (ni una página web, ni un correo, ni la IA) puede actuar en tu
nombre. Mira [Seguridad](security.md).

## ¿Cómo reporto un error o pido algo nuevo?

Abre un [issue en GitHub](https://github.com/inginddie/elissa/issues). Incluye tu versión (al final de *Ajustes*) y,
si sirve, la parte relevante de `logs/elissa.log` en tu [carpeta de datos](#donde-estan-mis-datos). Para problemas de
seguridad, mira [Seguridad](security.md#reportar-una-vulnerabilidad).
