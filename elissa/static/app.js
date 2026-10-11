import { Character } from './character.js';
import { native, shell } from './shell.js';
import { Sounds } from './sounds.js';

const $ = (s) => document.querySelector(s);
const face = new Character($('#face'));
const sfx = new Sounds(() => actx);

const STATUS = {
  waking: 'Despertando…',
  idle: 'Ctrl+Alt+Espacio o toca para hablar',
  listening: 'Escuchando…',
  transcribing: 'Transcribiendo…',
  thinking: 'Pensando…',
  speaking: 'Hablando',
  approval: 'Necesito tu aprobación',
  error: 'Error',
};

// Voice activity detection tuning (ms / RMS units)
const SILENCE_MS = 1100;
const NO_SPEECH_MS = 7000;
const MAX_LISTEN_MS = 60000;
const CALIBRATE_MS = 300; // first part of each listen measures the room's background noise
const MIC_IDLE_MS = 20000; // release the microphone (and Windows' mic indicator) after this long unused
const MIN_VOICED_MS = 220;

let ws;
let cfg = {};
let state = 'waking';
let ready = false;

// Turn bookkeeping: messages for any other turn are stale and ignored.
let currentTurn = -1;
let turnDone = true;
let replyText = '';
const history = [];

// Audio graph
let actx, micStream, micProc, outAnalyser;
let micLevel = 0;
let noiseFloor = 0.004;
const outBuf = new Float32Array(1024);

// Listening
let rec = null;
let chunks = [];
let vad = null;

// Speaking
let sayQueue = [];
let currentSrc = null;
let playing = false;

/* ---------- state & caption ---------- */

function setState(s, statusText) {
  const wasBusy = BUSY.has(state);
  if (s === 'error' && state !== 'error') sfx.play('error');
  state = s;
  document.body.dataset.state = s;
  face.setState(s === 'transcribing' ? 'thinking' : s);
  activity();
  $('#status').textContent = statusText ?? STATUS[s];
  if (wasBusy && !BUSY.has(s)) keepOpen(REPLY_LINGER_MS); // leave the answer readable for a moment
  updateMode();
}

/* ---------- window modes: compact (just the face) · talk (face + caption + controls) · panel ---------- */

const BUSY = new Set(['listening', 'transcribing', 'thinking', 'speaking', 'approval', 'error']);
const REPLY_LINGER_MS = 9000;
let mode = '';
let openUntil = 0;
let lingerTimer = null;

function desiredMode() {
  if (!$('#panel-approval').hidden) return 'approval';
  if (document.querySelector('.panel:not([hidden])')) return 'panel';
  if (BUSY.has(state) || performance.now() < openUntil) return 'talk';
  return 'compact';
}

function updateMode() {
  const m = desiredMode();
  if (m === mode) return;
  mode = m;
  document.body.dataset.mode = m;
  shell.setMode(m);
}

function keepOpen(ms) {
  openUntil = performance.now() + ms;
  clearTimeout(lingerTimer);
  lingerTimer = setTimeout(updateMode, ms + 50);
}

function showCaption(you, reply) {
  if (you !== undefined) $('#you').textContent = you ? `“${you}”` : '';
  if (reply !== undefined) $('#reply').textContent = reply;
  const c = $('#caption');
  c.scrollTop = c.scrollHeight;
}

function toIdle(statusText) {
  setState(ready ? 'idle' : 'waking', ready ? statusText : undefined);
  scheduleMicRelease();
}

/* ---------- audio ---------- */

async function ensureAudio(withMic = true) {
  if (!actx) {
    actx = new AudioContext();
    outAnalyser = actx.createAnalyser();
    outAnalyser.fftSize = 1024;
    outAnalyser.connect(actx.destination);
  }
  if (actx.state === 'suspended') await actx.resume().catch(() => {});
  clearTimeout(micTimer);
  if (withMic && !micStream) {
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
    });
    const src = actx.createMediaStreamSource(micStream);
    // ScriptProcessor runs on audio callbacks, so VAD keeps working while the window is in the background.
    micProc = actx.createScriptProcessor(2048, 1, 1);
    const mute = actx.createGain();
    mute.gain.value = 0;
    src.connect(micProc);
    micProc.connect(mute);
    mute.connect(actx.destination);
    micProc.onaudioprocess = (e) => onMicFrame(e.inputBuffer.getChannelData(0), e.inputBuffer.duration * 1000);
  }
}

let micTimer = null;

function scheduleMicRelease() {
  clearTimeout(micTimer);
  micTimer = setTimeout(() => {
    if (!micStream || state === 'listening' || (cfg.continuous && !turnDone)) return;
    micStream.getTracks().forEach((t) => t.stop());
    micProc.disconnect();
    micStream = micProc = null;
  }, MIC_IDLE_MS);
}

function outLevel() {
  if (!currentSrc) return 0;
  outAnalyser.getFloatTimeDomainData(outBuf);
  let s = 0;
  for (const x of outBuf) s += x * x;
  return Math.min(1, Math.sqrt(s / outBuf.length) * 5);
}

face.levelSource = () => {
  if (state === 'listening') return Math.min(1, micLevel / (Math.max(0.01, noiseFloor * 3) * 4));
  if (state === 'speaking') return outLevel();
  return 0;
};

/* ---------- listening ---------- */

function onMicFrame(data, ms) {
  let s = 0;
  for (let i = 0; i < data.length; i++) s += data[i] * data[i];
  const rms = Math.sqrt(s / data.length);
  micLevel = rms;
  if (!vad) return;
  const now = performance.now();
  if (now - vad.start < CALIBRATE_MS) {
    noiseFloor = noiseFloor * 0.6 + Math.min(rms, 0.05) * 0.4;
    return;
  }
  const threshold = Math.max(0.01, noiseFloor * 3);
  if (rms > threshold) {
    vad.voicedMs += ms;
    vad.lastVoice = now;
    if (vad.voicedMs > MIN_VOICED_MS) vad.speech = true;
  }
  if (vad.speech && now - vad.lastVoice > SILENCE_MS) stopListening(true);
  else if (!vad.speech && now - vad.start > NO_SPEECH_MS) stopListening(false);
  else if (now - vad.start > MAX_LISTEN_MS) stopListening(true);
}

let starting = false;

async function startListening() {
  // Only one recording at a time: two recorders writing into one upload produce an invalid audio file.
  if (rec || starting || state === 'listening' || state === 'transcribing') return;
  starting = true;
  try {
    // A microphone that was unplugged or switched leaves an ended track: get a fresh one.
    if (micStream && micStream.getAudioTracks().some((t) => t.readyState === 'ended')) {
      micStream.getTracks().forEach((t) => t.stop());
      micProc?.disconnect();
      micStream = micProc = null;
    }
    await ensureAudio();
  } catch (e) {
    setState('error', 'No tengo acceso al micrófono');
    return;
  } finally {
    starting = false;
  }
  if (rec) return;
  stopSpeech();
  startRecording();
  sfx.play('listen');
  setState('listening');
  showCaption('', '');
}

function startRecording() {
  const mine = []; // this recording's audio only, whatever else happens meanwhile
  chunks = mine;
  rec = new MediaRecorder(micStream, { mimeType: 'audio/webm;codecs=opus' });
  rec.chunks = mine;
  rec.ondataavailable = (e) => e.data.size && mine.push(e.data);
  rec.start(250);
  vad = { start: performance.now(), lastVoice: 0, voicedMs: 0, speech: false };
}

function stopListening(send, manual = false) {
  if (state !== 'listening' || !rec) return;
  const v = vad;
  const r = rec;
  vad = null;
  rec = null;
  if (!send) {
    // Synchronously, so a turn started right after this (e.g. typed text) isn't reset to idle later.
    r.stop();
    toIdle();
    return;
  }
  r.onstop = async () => {
    const hasSpeech = v.speech || (manual && v.voicedMs > 80);
    if (!send || !hasSpeech) {
      toIdle(cfg.continuous && !manual ? 'No escuché nada · toca para hablar' : undefined);
      return;
    }
    sfx.play('stop');
    setState('transcribing');
    try {
      const fd = new FormData();
      fd.append('file', new Blob(r.chunks, { type: 'audio/webm' }), 'audio.webm');
      const res = await fetch('/api/stt', { method: 'POST', body: fd });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setState('error', data.error || 'Falló el reconocimiento de voz');
        setTimeout(() => state === 'error' && toIdle(), 7000);
        return;
      }
      const { text } = data;
      if (!text) {
        toIdle('No te entendí, intenta de nuevo');
        return;
      }
      sendText(text);
    } catch {
      setState('error', 'Falló el reconocimiento de voz');
      setTimeout(() => state === 'error' && toIdle(), 7000);
    }
  };
  r.stop();
}

/* ---------- speaking ---------- */

function enqueueSay(text) {
  const job = fetch('/api/tts?text=' + encodeURIComponent(text))
    .then((r) => (r.ok ? r.arrayBuffer() : Promise.reject(r.status)))
    .then((buf) => actx.decodeAudioData(buf))
    .catch(() => null);
  sayQueue.push(job);
  if (!playing) playNext();
}

async function playNext() {
  if (!sayQueue.length) {
    playing = false;
    if (turnDone) finishTurn();
    return;
  }
  playing = true;
  const turn = currentTurn;
  if (state !== 'speaking') setState('speaking');
  const buf = await sayQueue.shift();
  if (turn !== currentTurn || !playing) return;
  if (!buf) return playNext();
  const src = actx.createBufferSource();
  src.buffer = buf;
  src.connect(outAnalyser);
  src.onended = () => {
    if (currentSrc === src) {
      currentSrc = null;
      playNext();
    }
  };
  currentSrc = src;
  src.start();
}

function stopSpeech() {
  sayQueue = [];
  playing = false;
  if (currentSrc) {
    const s = currentSrc;
    currentSrc = null;
    try { s.stop(); } catch {}
  }
}

function finishTurn() {
  if (state === 'listening') return;
  if (announcing) {
    announcing = false;
    toIdle();
    return;
  }
  if (turnStarted && performance.now() - turnStarted > LONG_TURN_MS) sfx.play('done');
  if (turnStarted) face.play('happy', 1100);
  turnStarted = 0;
  if (cfg.continuous) {
    setTimeout(() => state !== 'listening' && turnDone && !playing && startListening(), 350);
  } else {
    toIdle();
  }
}

/* ---------- conversation ---------- */

function sendText(text) {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    setState('error', 'Sin conexión con el servidor');
    return;
  }
  if (attached.length) {
    // the model gets the full paths; the history shows what the user said
    ws.send(JSON.stringify({ type: 'text', text: `[Archivos que te pasé: ${attached.join(' | ')}]\n${text}` }));
    attached = [];
    addHistory('user', text);
    showCaption(text, '');
    setState('thinking', ready ? undefined : 'Configura tu IA en Ajustes');
    turnStarted = performance.now();
    turnDone = false;
    return;
  }
  ensureAudio(false).catch(() => {});
  addHistory('user', text);
  showCaption(text, '');
  setState('thinking', ready ? undefined : 'Configura tu IA en Ajustes');
  turnStarted = performance.now();
  turnDone = false;
  ws.send(JSON.stringify({ type: 'text', text }));
}

function interrupt() {
  stopSpeech();
  if (!turnDone) {
    ws?.send(JSON.stringify({ type: 'interrupt' }));
    if (replyText) addHistory('assistant', replyText + ' …');
  }
  turnDone = true;
  currentTurn = -1;
}

function primaryAction() {
  if (approval) return; // the card needs a click: neither the shortcut nor the voice can answer it
  switch (state) {
    case 'listening':
      stopListening(true, true);
      break;
    case 'transcribing':
      break;
    case 'thinking':
    case 'speaking':
      interrupt();
      startListening();
      break;
    default:
      startListening();
  }
}

function silence() {
  if (state === 'listening') stopListening(false, true);
  else if (state === 'thinking' || state === 'speaking') {
    interrupt();
    toIdle();
  }
}

function handle(m) {
  switch (m.type) {
    case 'settings':
      applySettings(m.settings);
      break;
    case 'status':
      ready = m.configured;
      if (!ready) {
        setState('idle', 'Primero configura tu IA ⚙');
        if (!setupShownOnce) {
          setupShownOnce = true;
          openSetup();
        }
      } else if (state === 'waking' || (state === 'idle' && !m.busy)) {
        setState('idle');
        if (!greeted) {
          greeted = true;
          sfx.play('greet');
          face.play('happy', 1300);
        }
      }
      break;
    case 'turn':
      currentTurn = m.turn;
      turnDone = false;
      replyText = '';
      break;
    case 'tool':
      if (m.turn === currentTurn && state === 'thinking') {
        $('#status').textContent = m.name;
        face.setState('working');
      }
      break;
    case 'delta':
      if (m.turn !== currentTurn) break;
      replyText += m.text;
      showCaption(undefined, replyText.trim());
      break;
    case 'say':
      if (m.turn === currentTurn) enqueueSay(m.text);
      break;
    case 'done':
      if (m.turn !== currentTurn) break;
      turnDone = true;
      if (replyText.trim()) addHistory('assistant', replyText.trim());
      if (!playing && state !== 'error') finishTurn();
      break;
    case 'approval':
      showApproval(m);
      break;
    case 'approval_done':
      if (approval?.id === m.id) closeApproval();
      break;
    case 'reminder':
      announceReminder(m);
      break;
    case 'attached':
      onAttached(m.paths || []);
      break;
    case 'error':
      if (m.turn !== undefined && m.turn !== currentTurn) break;
      stopSpeech();
      turnDone = true;
      turnStarted = 0;
      setState('error', m.message);
      setTimeout(() => state === 'error' && toIdle(), 7000);
      break;
  }
}

function connect() {
  ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = (e) => handle(JSON.parse(e.data));
  ws.onclose = () => {
    ready = false;
    setState('waking', 'Reconectando…');
    setTimeout(connect, 1000);
  };
}

/* ---------- approvals ---------- */

let approval = null;

function el(tag, props = {}, ...children) {
  const e = Object.assign(document.createElement(tag), props);
  e.append(...children.filter((c) => c !== undefined && c !== null));
  return e;
}

function renderApprovalBody(m) {
  const body = $('#ap-body');
  body.innerHTML = '';
  if (m.kind === 'diff') {
    if (m.path) body.append(el('p', { className: 'hint', textContent: m.path }));
    const pre = el('pre');
    for (const line of String(m.diff || '').split('\n')) {
      const cls = line.startsWith('+') ? 'add' : line.startsWith('-') ? 'del' : line.startsWith('@@') ? 'meta' : '';
      pre.append(el('span', { className: cls, textContent: line + '\n' }));
    }
    body.append(pre);
  } else if (m.kind === 'email') {
    const dl = el('dl');
    for (const [k, v] of [['Para', m.to], ['CC', m.cc], ['Asunto', m.subject], ['Adjuntos', m.attachments]]) {
      if (v) dl.append(el('dt', { textContent: k }), el('dd', { textContent: v }));
    }
    body.append(dl, el('pre', { textContent: m.body || '' }));
  } else if (m.kind === 'action') {
    body.append(el('ul', {}, ...(m.lines || []).map((l) => el('li', { textContent: l }))));
  } else {
    body.append(el('pre', { textContent: m.text || '' }));
  }
}

function showApproval(m) {
  approval = m;
  $('#ap-title').textContent = m.title || 'Aprobar acción';
  $('#ap-sub').textContent = m.subtitle || '';
  $('#ap-sub').hidden = !m.subtitle;
  $('#ap-warn').textContent = m.warning || '';
  $('#ap-warn').hidden = !m.warning;
  renderApprovalBody(m);
  stopSpeech();
  document.querySelectorAll('.panel').forEach((p) => (p.hidden = p.id !== 'panel-approval'));
  $('#ap-ok').disabled = $('#ap-deny').disabled = false;
  setState('approval');
  sfx.play('approval');
  shell.show();
  $('#ap-deny').focus(); // the safe choice has the focus; approving takes a deliberate click
}

function closeApproval() {
  approval = null;
  $('#panel-approval').hidden = true;
  if (state === 'approval') setState('thinking');
  else updateMode();
}

function answerApproval(approved) {
  if (!approval) return;
  $('#ap-ok').disabled = $('#ap-deny').disabled = true;
  ws?.send(JSON.stringify({ type: 'approval_reply', id: approval.id, approved }));
  sfx.play(approved ? 'send' : 'close');
  if (!approved) face.play('annoyed', 700);
  closeApproval();
}

$('#ap-ok').addEventListener('click', (e) => {
  if (e.isTrusted) answerApproval(true); // a real click, never a scripted one
});
$('#ap-deny').onclick = () => answerApproval(false);

/* ---------- files dropped on Elissa ---------- */

let attached = [];

shell.on('tauri://drag-enter', () => {
  face.play('surprised', 60000);
  keepOpen(4000);
});
shell.on('tauri://drag-leave', () => face.play('idle', 10));
shell.on('tauri://drag-drop', ({ paths }) => {
  if (!paths?.length) return face.play('idle', 10);
  ws?.send(JSON.stringify({ type: 'attach', paths }));
});

function onAttached(paths) {
  if (!paths.length) {
    face.play('error', 1200);
    return;
  }
  attached = paths;
  const names = paths.map((p) => p.split(/[\\/]/).pop()).join(', ');
  face.play('happy', 1000);
  sfx.play('happy');
  shell.show();
  showCaption('', `Recibí ${names}. ¿Qué hago con ${paths.length > 1 ? 'ellos' : 'él'}?`);
  if (ready && (state === 'idle' || state === 'waking')) startListening();
}

/* ---------- reminders ---------- */

let announcing = false;

function announceReminder(m) {
  const who = cfg.user_name ? `${cfg.user_name}, ` : '';
  const late = m.late ? ' (llegó tarde porque estaba cerrada)' : '';
  const said = m.kind === 'timer' ? `${who}se acabó el tiempo. ${m.text}` : `${who}te recuerdo: ${m.text}`;
  shell.notify(m.kind === 'timer' ? 'Temporizador' : 'Recordatorio', m.text + late);
  sfx.play('done');
  face.play('surprised', 600);
  if (state === 'listening' || state === 'thinking' || state === 'approval' || state === 'speaking') {
    showCaption(undefined, said); // busy: show it, don't talk over the conversation
    return;
  }
  shell.show();
  showCaption('', said);
  announcing = true;
  turnDone = true;
  enqueueSay(said);
}

/* ---------- history panel ---------- */

function addHistory(role, text) {
  history.push({ role, text });
  renderHistory();
}

function renderHistory() {
  const log = $('#log');
  log.innerHTML = '';
  if (!history.length) {
    log.innerHTML = '<p class="empty">Aún no hemos hablado.</p>';
    return;
  }
  for (const { role, text } of history) {
    const d = document.createElement('div');
    d.className = `msg ${role}`;
    d.textContent = text;
    log.append(d);
  }
  log.scrollTop = log.scrollHeight;
}

/* ---------- settings & setup wizard ---------- */

let setupShownOnce = false;
let providers = [];

async function api(url, body) {
  const res = await fetch(url, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok && data.ok !== false, data };
}

function msg(el, text, kind = '') {
  el.textContent = text;
  el.className = `hint ${kind}`;
}

function applySettings(s) {
  cfg = s;
  document.title = `${s.name} · asistente de voz`;
  $('#btn-continuous').classList.toggle('on', !!s.continuous);
  $('#btn-pin').classList.toggle('on', !!s.pinned);
  for (const el of $('#settings').elements) {
    if (!el.name || !(el.name in s)) continue;
    if (el.type === 'checkbox') el.checked = !!s[el.name];
    else if (document.activeElement !== el) el.value = s[el.name];
  }
  $('#speed-val').textContent = `${Number(s.speed).toFixed(2)}×`;
  $('#stt-url-row').hidden = s.stt !== 'endpoint';
  sfx.enabled = s.sounds !== false;
  sfx.volume = Number(s.sound_volume ?? 0.6);
  shell.setPinned(!!s.pinned);
  refreshStt();
  $('#mail-enabled').checked = !!s.mail_enabled;
  if (document.activeElement !== $('#mail-user')) $('#mail-user').value = s.mail_user || '';
  if (document.activeElement !== $('#mail-server')) $('#mail-server').value = s.mail_server || '';
  renderFolders(s.allowed_folders || []);
  const p = providers.find((x) => x.id === s.provider);
  $('#ai-current').textContent = s.provider
    ? `Usando ${p ? p.label : s.provider} · ${s.model || 'modelo por defecto'}`
    : 'Sin configurar';
}

const STT_LABEL = { groq: 'Groq', openai: 'OpenAI', endpoint: 'tu servidor' };
const STT_KEY_URL = { groq: 'https://console.groq.com/keys', openai: 'https://platform.openai.com/api-keys' };

async function refreshStt() {
  const { data } = await api('/api/stt/status');
  const service = data.service;
  const wanted = cfg.stt === 'auto' ? 'groq' : cfg.stt; // auto without any key: suggest Groq
  const needsKey = (cfg.stt === 'groq' || cfg.stt === 'openai') || (cfg.stt === 'auto' && !service);
  $('#stt-status').textContent = service
    ? `Usando ${STT_LABEL[service]} para entender tu voz.`
    : 'Falta configurar cómo entender tu voz: pega una API key de Groq (gratis para empezar) u OpenAI.';
  $('#stt-key-row').hidden = !needsKey;
  $('#stt-key-label').textContent = `API key de ${STT_LABEL[wanted] || 'Groq'} para la voz`;
  $('#stt-key-link').href = STT_KEY_URL[wanted] || STT_KEY_URL.groq;
}

$('#stt-key-save').onclick = async () => {
  const provider = cfg.stt === 'openai' ? 'openai' : 'groq';
  const key = $('#stt-key').value.trim();
  if (!key) return;
  const { ok } = await api('/api/keys', { provider, api_key: key });
  $('#stt-key').value = '';
  if (ok) refreshStt();
};

async function saveSettings(changes) {
  const { ok, data } = await api('/api/settings', changes);
  if (!ok) $('#status').textContent = data.error || 'No se pudo guardar';
}

function renderFolders(folders) {
  const ul = $('#folders');
  ul.innerHTML = '';
  for (const f of folders) {
    const li = document.createElement('li');
    li.textContent = f;
    const rm = document.createElement('button');
    rm.type = 'button';
    rm.textContent = '×';
    rm.title = 'Quitar';
    rm.onclick = () => saveSettings({ allowed_folders: folders.filter((x) => x !== f) });
    li.append(rm);
    ul.append(li);
  }
}

async function loadVoices() {
  const sel = $('#voice-select');
  if (sel.options.length) return;
  try {
    const voices = await (await fetch('/api/voices')).json();
    for (const v of voices) sel.add(new Option(v.label, v.id));
  } catch {
    sel.add(new Option(cfg.voice, cfg.voice));
  }
  sel.value = cfg.voice;
}

async function loadProviders() {
  const { data } = await api('/api/providers');
  providers = data.providers || [];
  const sel = $('#setup-provider');
  sel.innerHTML = '';
  for (const p of providers) sel.add(new Option(p.label + (p.needs_key ? '' : ' · sin API key'), p.id));
  sel.value = data.current?.provider || 'openai';
  onProviderChange(false);
  $('#setup-url').value = data.current?.base_url || '';
  $('#setup-model').value = data.current?.model || '';
}

function onProviderChange(clearModel = true) {
  const p = providers.find((x) => x.id === $('#setup-provider').value);
  if (!p) return;
  $('#setup-key-row').hidden = !p.needs_key;
  $('#setup-url-row').hidden = p.id !== 'custom';
  $('#setup-key').value = '';
  $('#setup-key').placeholder = p.has_key ? 'Ya hay una clave guardada (deja vacío para usarla)' : 'Pega aquí tu clave';
  const link = $('#setup-key-link');
  link.href = p.key_url || '#';
  link.hidden = !p.key_url;
  link.textContent = p.needs_key ? '¿Dónde consigo la clave?' : `Instalar ${p.label}`;
  if (clearModel) $('#setup-model').value = p.suggested || '';
  $('#setup-model-row').hidden = clearModel;
  $('#setup-save').hidden = clearModel;
  msg($('#setup-msg'), '');
}

function setupBody() {
  return {
    provider: $('#setup-provider').value,
    api_key: $('#setup-key').value.trim(),
    base_url: $('#setup-url').value.trim(),
    model: $('#setup-model').value.trim(),
  };
}

async function openSetup() {
  await loadProviders();
  openPanel('panel-setup');
}

$('#setup-provider').onchange = () => onProviderChange(true);

$('#setup-test').onclick = async () => {
  msg($('#setup-msg'), 'Conectando…');
  const { ok, data } = await api('/api/providers/test', setupBody());
  if (!ok) return msg($('#setup-msg'), data.error || 'No pude conectar', 'err');
  const list = $('#setup-models');
  list.innerHTML = '';
  for (const m of data.models) list.append(new Option(m, m));
  const p = providers.find((x) => x.id === $('#setup-provider').value);
  if (!$('#setup-model').value) {
    $('#setup-model').value = data.models.includes(p?.suggested) ? p.suggested : (data.models[0] || '');
  }
  $('#setup-model-row').hidden = false;
  $('#setup-save').hidden = false;
  msg($('#setup-msg'), `Conectado: ${data.models.length} modelos disponibles. Elige uno y guarda.`, 'ok');
};

$('#setup-save').onclick = async () => {
  msg($('#setup-msg'), 'Guardando y probando el modelo…');
  const { ok, data } = await api('/api/providers/save', setupBody());
  if (!ok) return msg($('#setup-msg'), data.error || 'El modelo no respondió', 'err');
  msg($('#setup-msg'), `¡Listo! El modelo respondió: «${data.reply}»`, 'ok');
  setTimeout(() => openPanel(null), 1200);
};

$('#mail-save').onclick = async () => {
  msg($('#mail-msg'), 'Conectando con tu correo…');
  const { ok, data } = await api('/api/mail/save', {
    enabled: $('#mail-enabled').checked,
    user: $('#mail-user').value,
    password: $('#mail-pass').value,
    server: $('#mail-server').value,
  });
  $('#mail-pass').value = '';
  if (!ok) return msg($('#mail-msg'), data.error || 'No pude conectar', 'err');
  msg($('#mail-msg'), data.server ? `Conectado a ${data.server} (${data.status})` : data.status, 'ok');
};

function openPanel(id) {
  const wasOpen = !!document.querySelector('.panel:not([hidden])');
  document.querySelectorAll('.panel').forEach((p) => (p.hidden = p.id !== id));
  if (id && !wasOpen) sfx.play('open');
  if (!id && wasOpen) sfx.play('close');
  updateMode();
  if (id === 'panel-history') {
    renderHistory();
    $('#typed').focus();
  }
  if (id === 'panel-settings') {
    loadVoices();
    shell.getAutostart().then((on) => {
      $('#autostart').closest('label').hidden = on === null;
      $('#autostart').checked = !!on;
    });
    if (!providers.length) loadProviders().then(() => applySettings(cfg));
    fetch('/api/health')
      .then((r) => r.json())
      .then((h) => ($('#version').textContent = `Elissa ${h.version}`))
      .catch(() => {});
    shell.info().then((info) => showUpdate(info?.update));
  }
}

/* ---------- wiring ---------- */

$('#btn-main').onclick = () => (ready ? primaryAction() : openSetup());

// The face is both the talk button and the handle to move the window: a press that moves is a drag.
let press = null;
$('#face').addEventListener('pointerdown', (e) => {
  if (e.button === 0) press = { x: e.screenX, y: e.screenY, dragged: false };
});
$('#face').addEventListener('pointermove', (e) => {
  if (!press || press.dragged || !(e.buttons & 1)) return;
  if (Math.hypot(e.screenX - press.x, e.screenY - press.y) > 4) {
    press.dragged = true;
    shell.startDragging();
  }
});
$('#face').addEventListener('click', () => {
  const dragged = press?.dragged;
  press = null;
  if (!dragged) ready ? primaryAction() : openSetup();
});

/* ---------- character life: reactions, gaze, sleep ---------- */

const LONG_TURN_MS = 8000;
const SLEEP_AFTER_MS = 5 * 60 * 1000;
const HOVER_LOVE_MS = 2200;
let turnStarted = 0;
let greeted = false;
let lastActivity = performance.now();
let asleep = false;
let pokes = [];
let hoverTimer = null;
let lastLove = 0;
let lastDrag = 0;

function activity() {
  lastActivity = performance.now();
  if (asleep) {
    asleep = false;
    if (state === 'idle') face.setState('idle');
    sfx.play('wake');
  }
}

setInterval(() => {
  if (!asleep && state === 'idle' && mode === 'compact' && performance.now() - lastActivity > SLEEP_AFTER_MS) {
    asleep = true;
    face.setState('sleeping');
    sfx.play('sleep');
  }
}, 15000);

// Right click: a poke. Three in a row and she gets dizzy.
$('#face').addEventListener('contextmenu', (e) => {
  e.preventDefault();
  activity();
  const now = performance.now();
  pokes = pokes.filter((t) => now - t < 3000).concat(now);
  if (pokes.length >= 3) {
    pokes = [];
    face.play('dizzy', 2600);
    sfx.play('dizzy');
  } else {
    face.play('annoyed', 1100);
    sfx.play(pokes.length === 1 ? 'poke' : 'annoyed');
  }
});

// Resting the pointer on her for a moment: hearts (not too often).
$('#face').addEventListener('pointerenter', () => {
  clearTimeout(hoverTimer);
  hoverTimer = setTimeout(() => {
    if (state !== 'idle' || performance.now() - lastLove < 30000) return;
    lastLove = performance.now();
    face.play('love', 2200);
    sfx.play('love');
  }, HOVER_LOVE_MS);
});
$('#face').addEventListener('pointerleave', () => clearTimeout(hoverTimer));

// Her eyes follow the pointer: inside the window from page events, elsewhere from the shell.
document.addEventListener('pointermove', (e) => {
  face.lookAt(e.clientX, e.clientY);
  activity();
});
shell.on('cursor', ({ x, y }) => {
  face.lookAt(x, y);
  // the cursor coming close to her counts as activity (wakes her up)
  if (x > -150 && y > -150 && x < innerWidth + 150 && y < innerHeight + 150) activity();
});
shell.on('window-drag', () => {
  const now = performance.now();
  if (now - lastDrag > 1200) sfx.play('drag');
  lastDrag = now;
  face.play('surprised', 450);
});

$('#btn-compact').onclick = () => {
  silence();
  openUntil = 0;
  updateMode();
};
document.querySelectorAll('#mini [data-act]').forEach((b) => (b.onclick = (e) => {
  e.stopPropagation();
  const act = b.dataset.act;
  if (act === 'history') openPanel('panel-history');
  else if (act === 'settings') openPanel('panel-settings');
  else shell.hide();
}));
$('#autostart').onchange = async (e) => {
  try {
    e.target.checked = await shell.setAutostart(e.target.checked);
  } catch {
    e.target.checked = !e.target.checked;
  }
};

// Links open in the default browser, never inside Elissa's window.
document.addEventListener('click', (e) => {
  const a = e.target.closest('a[href^="http"]');
  if (!a) return;
  e.preventDefault();
  shell.openUrl(a.href);
});

function showUpdate(version) {
  $('#update-row').hidden = !version;
  if (version) $('#update-msg').textContent = `Hay una versión nueva: ${version}.`;
}

$('#update-btn').onclick = async () => {
  $('#update-btn').disabled = true;
  $('#update-msg').textContent = 'Descargando la actualización… Elissa se reiniciará sola.';
  try {
    await shell.installUpdate();
  } catch (e) {
    $('#update-btn').disabled = false;
    $('#update-msg').textContent = `No se pudo actualizar: ${e}`;
  }
};

shell.on('update-available', (version) => showUpdate(version));
shell.on('update-none', () => {
  openPanel('panel-settings');
  $('#update-row').hidden = false;
  $('#update-btn').hidden = true;
  $('#update-msg').textContent = 'Elissa está al día.';
  setTimeout(() => { $('#update-row').hidden = true; $('#update-btn').hidden = false; }, 6000);
});

shell.on('hotkey', () => (ready ? primaryAction() : openSetup()));
shell.on('shell-action', (action) => {
  if (action === 'settings') openPanel('panel-settings');
  if (action === 'reset') $('#reset').click();
  if (action === 'update') openPanel('panel-settings');
});
$('#btn-continuous').onclick = () => saveSettings({ continuous: !cfg.continuous });
$('#btn-pin').onclick = () => saveSettings({ pinned: !cfg.pinned });
$('#btn-history').onclick = () => openPanel('panel-history');
$('#btn-settings').onclick = () => openPanel('panel-settings');
$('#open-setup').onclick = () => openSetup();
document.querySelectorAll('[data-close]').forEach((b) => (b.onclick = () => openPanel(null)));

$('#typer').onsubmit = (e) => {
  e.preventDefault();
  const text = $('#typed').value.trim();
  if (!text) return;
  $('#typed').value = '';
  if (state === 'listening') stopListening(false, true);
  interrupt();
  openPanel(null);
  sfx.play('send');
  sendText(text);
};

const settingsForm = $('#settings');
settingsForm.addEventListener('change', (e) => {
  const el = e.target;
  if (!el.name) return;
  const value = el.type === 'checkbox' ? el.checked : el.type === 'range' ? Number(el.value) : el.value.trim();
  if (el.name === 'name' && !value) return;
  saveSettings({ [el.name]: value });
});
settingsForm.elements.speed.oninput = (e) => ($('#speed-val').textContent = `${Number(e.target.value).toFixed(2)}×`);

settingsForm.elements.sound_volume.oninput = (e) => (sfx.volume = Number(e.target.value));
settingsForm.elements.sound_volume.onchange = () => sfx.play('happy');
$('#sounds-folder').onclick = () => api('/api/sounds/open-folder', {});
$('#sounds-reload').onclick = async () => {
  await sfx.loadCustom((await api('/api/sounds')).data);
  sfx.play('greet');
};

$('#folder-add').onclick = async () => {
  const { path } = await (await fetch('/api/pick-folder', { method: 'POST' })).json();
  if (path && !cfg.allowed_folders.includes(path)) saveSettings({ allowed_folders: [...cfg.allowed_folders, path] });
};

$('#reset').onclick = () => {
  interrupt();
  history.length = 0;
  renderHistory();
  showCaption('', '');
  ws?.send(JSON.stringify({ type: 'reset' }));
  openPanel(null);
};

document.addEventListener('keydown', (e) => {
  if (e.target.matches('input, select')) return;
  if (e.key === 'Escape') {
    if (approval) return answerApproval(false);
    if (!document.querySelector('.panel:not([hidden])')) silence();
    openPanel(null);
  } else if (e.code === 'Space' && ready && !approval) {
    e.preventDefault();
    primaryAction();
  }
});

// UI errors end up in the engine's log (%APPDATA%\Elissa\logs), which is what a bug report can include.
function reportError(message) {
  try {
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'client_error', message: String(message) }));
  } catch {}
}
window.addEventListener('error', (e) => reportError(`${e.message} @ ${e.filename?.split('/').pop()}:${e.lineno}`));
window.addEventListener('unhandledrejection', (e) => reportError(`promise: ${e.reason?.stack || e.reason}`));

document.body.classList.toggle('native', native);
if (native) {
  // An app, not a browser: no page context menu (text fields keep theirs) and no reload/print/save/find keys.
  document.addEventListener('contextmenu', (e) => {
    if (!e.target.closest('input, textarea, .msg, #reply')) e.preventDefault();
  });
  document.addEventListener('keydown', (e) => {
    const k = e.key.toLowerCase();
    if (e.key === 'F5' || e.key === 'F3' || e.key === 'F7' || (e.altKey && /^arrow(left|right)$/.test(k))
      || ((e.ctrlKey || e.metaKey) && ['r', 'p', 's', 'f', 'g', 'u', 'j', 'h', 'n', 't', 'w', '+', '-', '=', '0'].includes(k))) {
      e.preventDefault();
    }
  }, true);
}
setState('waking');
connect();
ensureAudio(false)
  .then(async () => sfx.loadCustom((await api('/api/sounds')).data))
  .catch(() => {});
// Deep links: #ajustes opens settings, #configurar the AI setup (also used by tests/screenshots).
if (location.hash === '#ajustes') openPanel('panel-settings');
if (location.hash === '#configurar') {
  setupShownOnce = true;
  openSetup();
}
