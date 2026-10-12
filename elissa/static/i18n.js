// Interface language. The UI is written in Spanish; English comes from this dictionary. Static text in index.html
// is translated by walking the DOM; dynamic text goes through t(), with {name} placeholders for values.

const EN = {
  // window and status
  'Elissa · asistente de voz': 'Elissa · voice assistant',
  'Despertando…': 'Waking up…',
  'Ctrl+Alt+Espacio o toca para hablar': 'Ctrl+Alt+Space or tap to talk',
  'Escuchando…': 'Listening…',
  'Transcribiendo…': 'Transcribing…',
  'Pensando…': 'Thinking…',
  'Hablando': 'Speaking',
  'Necesito tu aprobación': 'I need your approval',
  'Error': 'Error',
  'Reconectando…': 'Reconnecting…',
  'Primero configura tu IA ⚙': 'Set up your AI first ⚙',
  'Configura tu IA en Ajustes': 'Set up your AI in Settings',
  'No escuché nada · toca para hablar': "I didn't hear anything · tap to talk",
  'No te entendí, intenta de nuevo': "I didn't catch that, try again",
  'No tengo acceso al micrófono': "I can't access the microphone",
  'Falló el reconocimiento de voz': 'Speech recognition failed',
  'Sin conexión con el servidor': 'No connection to the engine',
  'Toca para hablar · arrástrala para moverla': 'Tap to talk · drag to move',
  'Hablar (Ctrl+Alt+Espacio)': 'Talk (Ctrl+Alt+Space)',
  'Historial y escribir': 'History and typing',
  'Conversación continua': 'Continuous conversation',
  'Siempre visible': 'Always on top',
  'Ajustes': 'Settings',
  'Encoger': 'Shrink',
  'Escribir': 'Type',
  'Ocultar (sigue en la bandeja)': 'Hide (stays in the tray)',
  // conversation
  'Conversación': 'Conversation',
  'Escribe en vez de hablar…': 'Type instead of talking…',
  'Enviar': 'Send',
  'Aún no hemos hablado.': "We haven't talked yet.",
  'Recibí {names}. ¿Qué hago con {them}?': 'Got {names}. What should I do with {them}?',
  'ellos': 'them',
  'él': 'it',
  '{who}se acabó el tiempo. {text}': "{who}time's up. {text}",
  '{who}te recuerdo: {text}': '{who}a reminder: {text}',
  ' (llegó tarde porque estaba cerrada)': ' (late: Elissa was closed)',
  'Temporizador': 'Timer',
  'Recordatorio': 'Reminder',
  // approval card
  'Aprobar acción': 'Approve action',
  'Elissa solo lo hará si lo apruebas. La voz no puede aprobar.': 'Elissa will only do it if you approve. Voice cannot approve.',
  'Rechazar': 'Deny',
  'Aprobar': 'Approve',
  // setup wizard
  'Configura tu IA': 'Set up your AI',
  'Elige qué modelo de inteligencia artificial usará tu asistente. Puedes usar uno en la nube con tu propia API key o uno local y gratuito con Ollama.':
    'Choose the AI model your assistant will use: a cloud one with your own API key, or a free local one with Ollama.',
  'Proveedor': 'Provider',
  'URL del servidor (compatible con OpenAI)': 'Server URL (OpenAI-compatible)',
  'API key': 'API key',
  'Pega aquí tu clave': 'Paste your key here',
  'Ya hay una clave guardada (deja vacío para usarla)': 'A key is already saved (leave empty to use it)',
  '¿Dónde la consigo?': 'Where do I get it?',
  '¿Dónde consigo la clave?': 'Where do I get the key?',
  'Instalar {name}': 'Install {name}',
  'Conectar y ver modelos': 'Connect and list models',
  'Modelo': 'Model',
  'Guardar y probar': 'Save and test',
  'Tu API key se guarda cifrada en el Administrador de credenciales de Windows, nunca en archivos.':
    'Your API key is stored encrypted in the Windows Credential Manager, never in files.',
  'Conectando…': 'Connecting…',
  'No pude conectar': "Couldn't connect",
  'Conectado: {n} modelos disponibles. Elige uno y guarda.': 'Connected: {n} models available. Pick one and save.',
  'Guardando y probando el modelo…': 'Saving and testing the model…',
  'El modelo no respondió': "The model didn't answer",
  '¡Listo! El modelo respondió: «{reply}»': 'Done! The model answered: “{reply}”',
  ' · sin API key': ' · no API key',
  // settings
  'General': 'General',
  'Idioma': 'Language',
  'Automático (según Windows)': 'Automatic (from Windows)',
  'Nombre del asistente': "Assistant's name",
  'Tu nombre': 'Your name',
  'Para que te llame por tu nombre': 'So she calls you by your name',
  'Inteligencia artificial': 'Artificial intelligence',
  'Usando {provider} · {model}': 'Using {provider} · {model}',
  'modelo por defecto': 'default model',
  'Sin configurar': 'Not set up',
  'Cambiar proveedor o modelo': 'Change provider or model',
  'Voz': 'Voice',
  'Velocidad': 'Speed',
  'Reconocimiento de voz': 'Speech recognition',
  'Automático': 'Automatic',
  'Groq · muy rápido y económico': 'Groq · very fast and cheap',
  'En tu PC · privado, sin internet': 'On your PC · private, offline',
  'Servidor propio (Whisper u otro compatible)': 'Your own server (Whisper or compatible)',
  'Usando {service} para entender tu voz.': 'Using {service} to understand your voice.',
  'tu servidor': 'your server',
  'tu PC (whisper.cpp)': 'your PC (whisper.cpp)',
  'Falta configurar cómo entender tu voz: pega una API key de Groq (gratis para empezar) u OpenAI.':
    'Choose how to understand your voice: paste a Groq (free to start) or OpenAI API key.',
  'Lo que dices se transcribe en tu PC; nada sale a internet.': 'What you say is transcribed on your PC; nothing goes online.',
  'API key para la voz': 'API key for speech',
  'API key de {name} para la voz': '{name} API key for speech',
  'Pega aquí la clave': 'Paste the key here',
  'Guardar clave de voz': 'Save speech key',
  'Modelo local': 'Local model',
  'Rápido · 60 MB': 'Fast · 60 MB',
  'Más preciso · 190 MB': 'More accurate · 190 MB',
  'Usa whisper.cpp en tu computador: lo que dices nunca sale de tu PC. Se descarga una sola vez.':
    'Uses whisper.cpp on your computer: what you say never leaves your PC. Downloaded once.',
  'Estado: {status}': 'Status: {status}',
  'URL de transcripción': 'Transcription URL',
  'Despertarla diciendo «Hola Elissa» u «Oye Elissa» (con la voz en inglés: «Hey Elissa»)':
    'Wake her by saying «Hey Elissa», «Hi Elissa» or «Okay Elissa» (with her voice in Spanish: «Hola Elissa»)',
  'escuchando «Hola Elissa»': 'listening for «Hola Elissa»',
  'escuchando «Hey Elissa»': 'listening for «Hey Elissa»',
  'descargando {pct}%': 'downloading {pct}%',
  'en pausa (pantalla bloqueada)': 'paused (screen locked)',
  'sin micrófono, reintentando…': 'no microphone, retrying…',
  'Funciona sin internet: nada de lo que escucha sale de tu PC hasta que la despiertas. Mientras esté activa, Windows muestra el ícono del micrófono; se pausa sola con la pantalla bloqueada. La primera vez descarga un modelo de 40 MB.':
    'Works offline: nothing she hears leaves your PC until you wake her. While it is on, Windows shows the microphone icon; it pauses when the screen is locked. It downloads a 40 MB model the first time.',
  'Interrumpirla hablando mientras responde (mejor con audífonos)': 'Interrupt her by talking while she answers (best with headphones)',
  'Iniciar con Windows': 'Start with Windows',
  'Sonidos': 'Sounds',
  'Sonidos de Elissa': "Elissa's sounds",
  'Volumen': 'Volume',
  'Puedes cambiar cualquier sonido dejando un archivo con su nombre (por ejemplo': 'You can replace any sound by dropping a file with its name (for example',
  ') en la carpeta de sonidos.': ') in the sounds folder.',
  'Abrir carpeta de sonidos': 'Open sounds folder',
  'Recargar': 'Reload',
  'Correo': 'Email',
  'Permitir que lea mi correo': 'Let her read my email',
  'Permitir que envíe correos (siempre te los mostraré antes y esperaré tu aprobación)': "Let her send email (you'll always see it first and approve it)",
  'Dirección': 'Address',
  'Contraseña de aplicación': 'App password',
  '16 caracteres, no tu contraseña normal': '16 characters, not your normal password',
  'Servidor IMAP': 'IMAP server',
  'se detecta solo (imap.gmail.com…)': 'detected automatically (imap.gmail.com…)',
  'Gmail: activa la verificación en dos pasos y crea la contraseña en': 'Gmail: turn on 2-step verification and create the password at',
  '. Elissa nunca borra ni marca correos como leídos, y solo envía lo que apruebes.': '. Elissa never deletes or marks email as read, and only sends what you approve.',
  'Probar y guardar correo': 'Test and save email',
  'Conectando con tu correo…': 'Connecting to your email…',
  'Conectado a {server} ({status})': 'Connected to {server} ({status})',
  'Integraciones (MCP)': 'Integrations (MCP)',
  'Conecta a Elissa con otros servicios mediante servidores MCP. Lo que solo lee es libre; todo lo que cambia algo te pide aprobación.':
    'Connect Elissa to other services through MCP servers. Read-only tools run freely; anything that changes something asks you first.',
  'Agregar': 'Add',
  'Elige un servicio…': 'Choose a service…',
  'Otro servidor MCP…': 'Other MCP server…',
  'Nombre': 'Name',
  'Mi servidor': 'My server',
  'Conexión': 'Connection',
  'Remota (URL, Streamable HTTP)': 'Remote (URL, Streamable HTTP)',
  'Programa local (comando)': 'Local program (command)',
  'URL': 'URL',
  'Comando': 'Command',
  'Token': 'Token',
  'Token (opcional, se envía como «Authorization: Bearer …»)': 'Token (optional, sent as “Authorization: Bearer …”)',
  '¿Cómo lo consigo?': 'How do I get it?',
  'Conectar': 'Connect',
  'Falta: {what}': 'Missing: {what}',
  'Usa solo servidores en los que confíes: pueden ejecutar programas en tu PC.': 'Only use servers you trust: they can run programs on your PC.',
  'Activado': 'Enabled',
  'Quitar': 'Remove',
  'Uso del computador': 'Using the computer',
  'Permitir que vea y use otras ventanas': 'Let her see and use other windows',
  'Leer una ventana, hacer clic, escribir o presionar teclas siempre te pide aprobación. Nunca lee campos de contraseña.':
    'Reading a window, clicking, typing or pressing keys always asks for approval. Password fields are never read.',
  'Carpetas que puede usar': 'Folders she can use',
  'Agregar carpeta': 'Add folder',
  'Memoria': 'Memory',
  'Al terminar cada conversación, Elissa la resume y guarda lo importante. Atajo global:': 'After each conversation Elissa summarizes it and keeps what matters. Global shortcut:',
  'Espacio': 'Space',
  'para hablar o interrumpir;': 'to talk or interrupt;',
  'para callarla.': 'to silence her.',
  'Nueva conversación': 'New conversation',
  'Actualizar ahora': 'Update now',
  'Hay una versión nueva: {version}.': 'A new version is available: {version}.',
  'Descargando la actualización… Elissa se reiniciará sola.': 'Downloading the update… Elissa will restart by herself.',
  'No se pudo actualizar: {error}': "Couldn't update: {error}",
  'Elissa está al día.': 'Elissa is up to date.',
  'No se pudo guardar': "Couldn't save",
  'Atajo para hablar': 'Shortcut to talk',
  'Hablar': 'Talk',
  'Haz clic y presiona la combinación…': 'Click and press the combination…',
  'Atajo guardado: {combo}': 'Shortcut saved: {combo}',
  'No pude registrar ese atajo; puede que otra app lo use.': "Couldn't register that shortcut; another app may be using it.",
};

let lang = 'es';
const originals = new WeakMap(); // node -> Spanish text, so switching back restores it

export function setLang(l) {
  lang = l === 'en' ? 'en' : 'es';
  document.documentElement.lang = lang;
}

export function currentLang() {
  return lang;
}

/** Translates a Spanish UI string; {name} placeholders are filled from vars (in either language). */
export function t(text, vars = {}) {
  const out = lang === 'en' ? (EN[text] ?? text) : text;
  return out.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m));
}

const norm = (s) => s.replace(/\s+/g, ' ').trim();

/** Translates the static text of the page (text nodes and placeholder/title attributes). */
export function translateDom(root = document.body) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (node.parentElement?.closest('script, style, [data-no-i18n]')) continue;
    if (!originals.has(node)) originals.set(node, node.nodeValue);
    const source = originals.get(node);
    const key = norm(source);
    if (!key || !(key in EN)) continue;
    const lead = source.match(/^\s*/)[0];
    const trail = source.match(/\s*$/)[0];
    node.nodeValue = lang === 'en' ? lead + EN[key] + trail : source;
  }
  for (const el of root.querySelectorAll('[placeholder], [title], option')) {
    for (const attr of ['placeholder', 'title']) {
      if (!el.hasAttribute(attr)) continue;
      const store = `i18n${attr}`;
      if (!(store in el.dataset)) el.dataset[store] = el.getAttribute(attr);
      const source = el.dataset[store];
      el.setAttribute(attr, lang === 'en' ? (EN[norm(source)] ?? source) : source);
    }
  }
}

/** The language to use: the saved choice, or Windows' (the WebView's) language. */
export function resolveLang(setting) {
  if (setting === 'es' || setting === 'en') return setting;
  return (navigator.language || 'es').toLowerCase().startsWith('es') ? 'es' : 'en';
}
