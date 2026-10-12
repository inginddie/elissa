# Primeros pasos

## 1. Configura tu IA

La primera vez, Elissa abre **Configura tu IA**:

1. Elige un **proveedor**. Ollama y LM Studio corren en tu computador y no necesitan clave.
2. Pega tu **API key**. *¿Dónde la consigo?* te lleva a la página del proveedor.
3. Elige **Conectar y ver modelos**. Elissa prueba la clave y lista los modelos que tu cuenta puede usar.
4. Elige un **modelo** (hay uno sugerido) y luego **Guardar y probar**.

| Proveedor | Clave | Notas |
|---|:-:|---|
| OpenAI | :material-check: | Modelos GPT |
| Anthropic | :material-check: | Modelos Claude |
| Google Gemini | :material-check: | |
| OpenRouter | :material-check: | Cientos de modelos con una sola clave |
| Groq | :material-check: | Muy rápido; también es el servicio de voz recomendado |
| Ollama | — | Gratis y 100 % local. Primero [instala Ollama](https://ollama.com) |
| LM Studio | — | Gratis y 100 % local. Primero [instala LM Studio](https://lmstudio.ai) |
| Otro compatible con OpenAI | opcional | Indícale a Elissa su URL |

Tu clave se guarda en el llavero de tu sistema (Administrador de credenciales de Windows, Llavero de macOS o Secret
Service de Linux), nunca en un archivo. Puedes cambiar de proveedor o modelo después en
*Ajustes → Inteligencia artificial*.

## 2. Que te escuche

Abre *Ajustes* (el engranaje) → **Voz** → **Reconocimiento de voz** y elige cómo te entiende:

- **Groq**: muy rápido y económico, gratis para empezar. Pega una [clave de Groq](https://console.groq.com/keys).
- **OpenAI**: pega una [clave de OpenAI](https://platform.openai.com/api-keys).
- **En tu PC** (Windows): privado y sin internet. Descarga whisper.cpp y un modelo de 60 MB una sola vez.
- **Servidor propio**: cualquier URL de transcripción compatible con Whisper.

Con **Automático**, Elissa usa lo que haya disponible: el servicio de voz de tu proveedor de chat, cualquier clave de
Groq u OpenAI que hayas guardado, tu servidor, o el reconocimiento en tu PC si está instalado.

## 3. Habla

| Acción | Cómo |
|---|---|
| Hablar | Di «Hola Elissa», presiona ++ctrl+alt+space++ desde cualquier lugar, haz clic en su cara o presiona ++space++ en su ventana |
| Interrumpirla | El mismo atajo mientras piensa o habla, o simplemente habla si *Interrumpirla hablando* está activo |
| Callarla | ++esc++ en su ventana |
| Terminar la conversación | «Listo, gracias», «chao», «eso es todo» |
| Escribir en vez de hablar | El botón de chat |
| Moverla | Arrástrala de la cara |
| Esconderla | El botón ⌄, el ícono de la bandeja, o di «escóndete»; el atajo la trae de vuelta |
| Darle un archivo | Suéltalo sobre su ventana y pregúntale por él |

Con **Conversación continua** activa (viene así), vuelve a escuchar después de cada respuesta, así que puedes seguir
hablando sin el atajo.

Para despertarla con la voz, activa la frase en *Ajustes → Voz*. La primera vez descarga un modelo de 40 MB; después
funciona sin internet y se pausa mientras la pantalla está bloqueada.

## 4. Aprueba lo que hace

Cuando Elissa quiere cambiar algo (escribir un archivo, enviar un correo, correr un comando, hacer clic en una
ventana) muestra una **tarjeta de aprobación** con exactamente lo que va a pasar: el diff, el correo completo, el
comando tal como se va a ejecutar. Solo un clic real en la tarjeta lo aprueba. Ni tu voz, ni el atajo, ni la IA
pueden. ++esc++ lo rechaza.

Leer cosas (archivos en tus carpetas permitidas, la web, tu correo si lo activaste) no necesita tarjeta.

## 5. Hazla tuya

- *Ajustes → General*: su nombre, tu nombre y el idioma de la interfaz (español o inglés).
- *Ajustes → Voz*: su voz y velocidad, y si inicia con el sistema.
- *Ajustes → Carpetas que puede usar*: por defecto, tu carpeta personal.
- *Ajustes → Sonidos*: volumen, o [tus propios sonidos](settings.md#sonidos).

Sigue con [todo lo que le puedes pedir](voice-commands.md).
