import { Character } from './character.js';
import { native, shell } from './shell.js';
import { Sounds } from './sounds.js';
import { currentLang, resolveLang, setLang, t, translateDom } from './i18n.js';

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
const MAX_LISTEN_MS = 20000;
const CALIBRATE_MS = 300; // first part of each listen measures the room's background noise
const DUCK_SETTLE_MS = 150; // other apps are being turned down meanwhile: measure the room after that
const VOICE_DROP = 0.3; // once you speak, sound this far below your own voice counts as silence (music)
const MIC_IDLE_MS = 20000; // release the microphone (and Windows' mic indicator) after this long unused
const MIN_VOICED_MS = 220;
const BARGE_IN_MS = 350; // the user's voice over Elissa's for this long interrupts her

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
  if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ui_state', state: s }));
  $('#status').textContent = statusText ?? t(STATUS[s]);
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
    if (!micStream || state === 'listening' || state === 'speaking' || (cfg.continuous && !turnDone)) return;
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

let bargeMs = 0;

function onMicFrame(data, ms) {
  if (rec?.wav) rec.chunks.push(new Float32Array(data)); // copy: the node reuses its buffer
  if (state === 'speaking' && cfg.barge_in) {
    checkBargeIn(data, ms);
    return;
  }
  let s = 0;
  for (let i = 0; i < data.length; i++) s += data[i] * data[i];
  const rms = Math.sqrt(s / data.length);
  micLevel = rms;
  if (!vad) return;
  const now = performance.now();
  const since = now - vad.start;
  if (since < DUCK_SETTLE_MS) return;
  if (since < DUCK_SETTLE_MS + CALIBRATE_MS) {
    noiseFloor = noiseFloor * 0.6 + Math.min(rms, 0.05) * 0.4;
    return;
  }
  // The background keeps being learned: quiet moments pull the floor down, and a steady louder background (music)
  // slowly pushes it up before you start talking, so the music itself doesn't count as speech.
  if (rms < noiseFloor * 1.5) noiseFloor = noiseFloor * 0.95 + rms * 0.05;
  else if (!vad.speech) noiseFloor = Math.min(noiseFloor * 1.003, 0.05);
  const threshold = Math.max(0.01, noiseFloor * 3);
  // After you start, only sound near your own voice level counts: music left in the background reads as silence.
  if (rms > threshold && (!vad.speech || rms > vad.peak * VOICE_DROP)) {
    vad.voicedMs += ms;
    vad.lastVoice = now;
    vad.peak = Math.max(vad.peak * 0.998, rms);
    if (vad.voicedMs > MIN_VOICED_MS) vad.speech = true;
  }
  if (vad.speech && now - vad.lastVoice > SILENCE_MS) stopListening(true);
  else if (!vad.speech && now - vad.start > NO_SPEECH_MS) stopListening(false);
  else if (now - vad.start > MAX_LISTEN_MS) stopListening(true);
}

let starting = false;

/**
 * Talking over Elissa: the microphone level must stay well above both the room noise and what is left of her own
 * voice after echo cancellation, for BARGE_IN_MS in a row.
 */
function checkBargeIn(data, ms) {
  let s = 0;
  for (let i = 0; i < data.length; i++) s += data[i] * data[i];
  const rms = Math.sqrt(s / data.length);
  const echo = outLevel() / 5; // outLevel() is scaled ×5 for the mouth animation
  const loud = rms > Math.max(0.03, noiseFloor * 5) && rms > echo * 0.6;
  bargeMs = loud ? bargeMs + ms : Math.max(0, bargeMs - ms);
  if (bargeMs >= BARGE_IN_MS) {
    bargeMs = 0;
    interrupt();
    setState('idle');
    startListening();
  }
}

async function startListening(auto = false) {
  if (!auto) conversationOver = false; // called again by the user: a new conversation
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
    setState('error', t('No tengo acceso al micrófono'));
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
  if (sttService === 'local') {
    // whisper.cpp reads WAV: keep the raw samples the microphone node already delivers
    rec = { wav: true, chunks: mine, stop() { setTimeout(() => this.onstop?.(), 0); } };
  } else {
    rec = new MediaRecorder(micStream, { mimeType: 'audio/webm;codecs=opus' });
    rec.chunks = mine;
    rec.ondataavailable = (e) => e.data.size && mine.push(e.data);
    rec.start(250);
  }
  vad = { start: performance.now(), lastVoice: 0, voicedMs: 0, speech: false, peak: 0 };
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
      toIdle(cfg.continuous && !manual ? t('No escuché nada · toca para hablar') : undefined);
      return;
    }
    sfx.play('stop');
    setState('transcribing');
    try {
      const fd = new FormData();
      if (r.wav) fd.append('file', encodeWav(r.chunks, actx.sampleRate), 'audio.wav');
      else fd.append('file', new Blob(r.chunks, { type: 'audio/webm' }), 'audio.webm');
      const res = await fetch('/api/stt', { method: 'POST', body: fd });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setState('error', data.error || t('Falló el reconocimiento de voz'));
        setTimeout(() => state === 'error' && toIdle(), 7000);
        return;
      }
      const { text } = data;
      if (!text) {
        toIdle(t('No te entendí, intenta de nuevo'));
        return;
      }
      const local = localCommand(text);
      if (local) {
        addHistory('user', text);
        showCaption(text, '');
        endConversation(local === 'hide');
        return;
      }
      sendText(text);
    } catch {
      setState('error', t('Falló el reconocimiento de voz'));
      setTimeout(() => state === 'error' && toIdle(), 7000);
    }
  };
  r.stop();
}

/* ---------- ending the conversation by voice ---------- */

// Whole utterances only (after an optional "Elissa"), so these words inside a real request never end anything.
const END_PHRASES = ['listo', 'listo gracias', 'gracias', 'muchas gracias', 'eso es todo', 'eso seria todo',
  'gracias eso es todo', 'nada mas', 'ya', 'ya esta', 'chao', 'chau', 'adios', 'hasta luego', 'termina', 'terminar',
  'finaliza', 'finalizar', 'deja de escuchar', 'para de escuchar', 'thanks', 'thank you', 'thats all',
  'thats all thanks', 'thank you thats all', 'bye', 'goodbye', 'stop listening', 'nothing else', 'done', 'im done'];
const HIDE_PHRASES = ['minimizate', 'minimizar', 'minimiza', 'escondete', 'ocultate', 'vete', 'desaparece',
  'minimize', 'hide', 'go away'];

function normalizeSpoken(text) {
  return text.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9 ]/g, '')
    .replace(/\s+/g, ' ').trim().replace(/^(hola |oye |hey |ok |okay )?(elissa|elisa|alyssa)\s*/, '').trim();
}

function localCommand(text) {
  const said = normalizeSpoken(text);
  if (HIDE_PHRASES.includes(said)) return 'hide';
  if (END_PHRASES.includes(said)) return 'end';
  return '';
}

let conversationOver = false; // set when the user says goodbye: continuous mode stops listening until called again
let hideAfterTurn = false;

function endConversation(hide) {
  conversationOver = true;
  sfx.play('close');
  face.play('happy', 900);
  toIdle();
  if (hide) setTimeout(() => shell.hide(), 700);
}

/** Float32 chunks at the context's rate -> 16 kHz mono 16-bit WAV (averaging down-sampler). */
function encodeWav(chunks, rate) {
  const total = chunks.reduce((n, c) => n + c.length, 0);
  const ratio = rate / 16000;
  const out = new Int16Array(Math.floor(total / ratio));
  let pos = 0;
  let acc = 0;
  let count = 0;
  let next = ratio;
  let i = 0;
  for (const c of chunks) {
    for (const x of c) {
      acc += x;
      count++;
      i++;
      if (i >= next && pos < out.length) {
        out[pos++] = Math.max(-1, Math.min(1, acc / count)) * 0x7fff;
        acc = count = 0;
        next += ratio;
      }
    }
  }
  const buf = new ArrayBuffer(44 + out.length * 2);
  const v = new DataView(buf);
  const str = (o, s) => [...s].forEach((ch, k) => v.setUint8(o + k, ch.charCodeAt(0)));
  str(0, 'RIFF'); v.setUint32(4, 36 + out.length * 2, true); str(8, 'WAVE'); str(12, 'fmt ');
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, 16000, true);
  v.setUint32(28, 32000, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); str(36, 'data');
  v.setUint32(40, out.length * 2, true);
  new Int16Array(buf, 44).set(out);
  return new Blob([buf], { type: 'audio/wav' });
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
  if (state !== 'speaking') {
    setState('speaking');
    bargeMs = 0;
    if (cfg.barge_in) ensureAudio(true).catch(() => {}); // listen while she talks
  }
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
  if (hideAfterTurn) {
    hideAfterTurn = false;
    toIdle();
    setTimeout(() => shell.hide(), 700);
  } else if (cfg.continuous && !conversationOver) {
    setTimeout(() => state !== 'listening' && turnDone && !playing && !conversationOver && startListening(true), 350);
  } else {
    toIdle();
  }
}

/* ---------- conversation ---------- */

function sendText(text) {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    setState('error', t('Sin conexión con el servidor'));
    return;
  }
  if (attached.length) {
    // the model gets the full paths; the history shows what the user said
    ws.send(JSON.stringify({ type: 'text', text: `[Archivos que te pasé: ${attached.join(' | ')}]\n${text}` }));
    attached = [];
    addHistory('user', text);
    showCaption(text, '');
    setState('thinking', ready ? undefined : t('Configura tu IA en Ajustes'));
    turnStarted = performance.now();
    turnDone = false;
    return;
  }
  ensureAudio(false).catch(() => {});
  addHistory('user', text);
  showCaption(text, '');
  setState('thinking', ready ? undefined : t('Configura tu IA en Ajustes'));
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
        setState('idle', t('Primero configura tu IA ⚙'));
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
    case 'agent_alert':
      announceAgent(m);
      break;
    case 'end_conversation':
      conversationOver = true;
      hideAfterTurn = !!m.hide;
      break;
    case 'spotify':
      if (m.connected) msg($('#spotify-msg'), t('Spotify quedó conectado.'), 'ok');
      if (!$('#panel-settings').hidden) loadSpotify();
      break;
    case 'attached':
      onAttached(m.paths || []);
      break;
    case 'wake':
      if (!ready || approval || !['idle', 'waking', 'error'].includes(state)) break;
      shell.show();
      face.play('surprised', 350);
      startListening();
      break;
    case 'mcp_status':
      if (!$('#panel-settings').hidden) loadMcp();
      break;
    case 'stt_local_status':
      showLocalStatus(m.status);
      if (m.status === 'listo') refreshStt();
      break;
    case 'wake_status':
      $('#wake-status').textContent = m.status && m.status !== 'apagado' ? t('Estado: {status}', { status: wakeStatus(m.status) }) : '';
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
    setState('waking', t('Reconectando…'));
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
  } else if (m.kind === 'command') {
    body.append(el('p', { className: 'hint', textContent: m.cwd || '' }));
    body.append(el('pre', { className: 'cmd', textContent: `> ${m.command || ''}` }));
  } else if (m.kind === 'action') {
    body.append(el('ul', {}, ...(m.lines || []).map((l) => el('li', { textContent: l }))));
  } else {
    body.append(el('pre', { textContent: m.text || '' }));
  }
}

function showApproval(m) {
  approval = m;
  $('#ap-title').textContent = m.title || t('Aprobar acción');
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
  showCaption('', t('Recibí {names}. ¿Qué hago con {them}?', { names, them: t(paths.length > 1 ? 'ellos' : 'él') }));
  if (ready && (state === 'idle' || state === 'waking')) startListening();
}

/* ---------- reminders ---------- */

let announcing = false;

function announceReminder(m) {
  const who = cfg.user_name ? `${cfg.user_name}, ` : '';
  const late = m.late ? t(' (llegó tarde porque estaba cerrada)') : '';
  const said = t(m.kind === 'timer' ? '{who}se acabó el tiempo. {text}' : '{who}te recuerdo: {text}', { who, text: m.text });
  shell.notify(t(m.kind === 'timer' ? 'Temporizador' : 'Recordatorio'), m.text + late);
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
    log.replaceChildren(el('p', { className: 'empty', textContent: t('Aún no hemos hablado.') }));
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

/* ---------- global shortcut ---------- */

const KEY_NAMES = { ' ': 'space', ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right' };
let hotkeyApplied = '';

const prettyHotkey = (combo) => combo.split('+').map((k) => (k === 'space' ? t('Espacio') : k.length === 1 ? k.toUpperCase()
  : k[0].toUpperCase() + k.slice(1))).join('+');

async function applyHotkey(combo) {
  combo = combo || 'ctrl+alt+space';
  if (document.activeElement !== $('#hotkey')) $('#hotkey').value = prettyHotkey(combo);
  $('#btn-main').title = `${t('Hablar')} (${prettyHotkey(combo)})`;
  if (combo === hotkeyApplied || !native) return;
  try {
    await shell.setHotkey(combo);
    hotkeyApplied = combo;
  } catch {
    $('#hotkey-msg').textContent = t('No pude registrar ese atajo; puede que otra app lo use.');
  }
}

$('#hotkey').addEventListener('keydown', async (e) => {
  e.preventDefault();
  e.stopPropagation();
  const key = KEY_NAMES[e.key] || e.key;
  if (['Control', 'Alt', 'Shift', 'Meta'].includes(key)) return; // wait for the main key
  const mods = [e.ctrlKey && 'ctrl', e.altKey && 'alt', e.shiftKey && 'shift', e.metaKey && 'super'].filter(Boolean);
  if (!mods.length || (mods.length === 1 && mods[0] === 'shift')) return; // a bare key would steal normal typing
  const main = /^F\d{1,2}$/.test(key) ? key.toLowerCase() : key.length === 1 ? key.toLowerCase() : key.toLowerCase();
  const combo = [...mods, main].join('+');
  try {
    if (native) await shell.setHotkey(combo);
    hotkeyApplied = combo;
    await saveSettings({ hotkey: combo });
    $('#hotkey').value = prettyHotkey(combo);
    $('#hotkey-msg').textContent = t('Atajo guardado: {combo}', { combo: prettyHotkey(combo) });
  } catch {
    $('#hotkey-msg').textContent = t('No pude registrar ese atajo; puede que otra app lo use.');
  }
});

/* ---------- language ---------- */

let languageSynced = false;

function applyLanguage(setting) {
  const lang = resolveLang(setting);
  // First run on an English Windows: speech follows the interface unless the user chose otherwise.
  if (setting === 'auto' && !cfg.language_autosynced && !languageSynced) {
    languageSynced = true;
    const changes = { language_autosynced: true };
    if (cfg.language && !cfg.language.startsWith(lang)) {
      Object.assign(changes, { language: lang === 'en' ? 'en-US' : 'es-CO',
        voice: lang === 'en' ? 'en-US-AvaNeural' : 'es-CO-SalomeNeural' });
    }
    saveSettings(changes);
  }
  if (lang === currentLang() && document.body.dataset.lang === lang) return;
  setLang(lang);
  document.body.dataset.lang = lang;
  translateDom();
  if (state) $('#status').textContent = t(STATUS[state] || '');
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
  document.title = `${s.name} · ${t('Elissa · asistente de voz').split(' · ')[1]}`;
  applyLanguage(s.ui_language);
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
  applyHotkey(s.hotkey);
  refreshStt();
  $('#mail-enabled').checked = !!s.mail_enabled;
  if (document.activeElement !== $('#mail-user')) $('#mail-user').value = s.mail_user || '';
  if (document.activeElement !== $('#mail-server')) $('#mail-server').value = s.mail_server || '';
  renderFolders(s.allowed_folders || []);
  const p = providers.find((x) => x.id === s.provider);
  $('#ai-current').textContent = s.provider
    ? t('Usando {provider} · {model}', { provider: p ? p.label : s.provider, model: s.model || t('modelo por defecto') })
    : t('Sin configurar');
}

const STT_LABEL = { groq: 'Groq', openai: 'OpenAI', endpoint: 'tu servidor', local: 'tu PC (whisper.cpp)' };

/** The wake listener reports its status in Spanish; translate it for the English interface. */
function wakeStatus(status) {
  const pct = status.match(/^descargando (\d+)%$/);
  return pct ? t('descargando {pct}%', { pct: pct[1] }) : t(status);
}

function showLocalStatus(status) {
  $('#stt-local-status').textContent = status ? t('Estado: {status}', { status }) : '';
}
const STT_KEY_URL = { groq: 'https://console.groq.com/keys', openai: 'https://platform.openai.com/api-keys' };

let sttService = null;

async function refreshStt() {
  const { data } = await api('/api/stt/status');
  const service = data.service;
  sttService = service;
  $('#stt-local-row').hidden = cfg.stt !== 'local';
  if (data.local) showLocalStatus(data.local.installed && !data.local.status ? 'listo' : data.local.status);
  const wanted = cfg.stt === 'auto' ? 'groq' : cfg.stt; // auto without any key: suggest Groq
  const needsKey = (cfg.stt === 'groq' || cfg.stt === 'openai') || (cfg.stt === 'auto' && !service);
  if (cfg.stt === 'local') {
    $('#stt-status').textContent = t('Lo que dices se transcribe en tu PC; nada sale a internet.');
    $('#stt-key-row').hidden = true;
    return;
  }
  $('#stt-status').textContent = service
    ? t('Usando {service} para entender tu voz.', { service: t(STT_LABEL[service]) })
    : t('Falta configurar cómo entender tu voz: pega una API key de Groq (gratis para empezar) u OpenAI.');
  $('#stt-key-row').hidden = !needsKey;
  $('#stt-key-label').textContent = t('API key de {name} para la voz', { name: STT_LABEL[wanted] || 'Groq' });
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
  if (!ok) $('#status').textContent = data.error || t('No se pudo guardar');
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
  if (sel.options.length > 1) return;
  sel.innerHTML = '';
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
  for (const p of providers) sel.add(new Option(p.label + (p.needs_key ? '' : t(' · sin API key')), p.id));
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
  $('#setup-key').placeholder = t(p.has_key ? 'Ya hay una clave guardada (deja vacío para usarla)' : 'Pega aquí tu clave');
  const link = $('#setup-key-link');
  link.href = p.key_url || '#';
  link.hidden = !p.key_url;
  link.textContent = p.needs_key ? t('¿Dónde consigo la clave?') : t('Instalar {name}', { name: p.label });
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
  msg($('#setup-msg'), t('Conectando…'));
  const { ok, data } = await api('/api/providers/test', setupBody());
  if (!ok) return msg($('#setup-msg'), data.error || t('No pude conectar'), 'err');
  const list = $('#setup-models');
  list.innerHTML = '';
  for (const m of data.models) list.append(new Option(m, m));
  const p = providers.find((x) => x.id === $('#setup-provider').value);
  if (!$('#setup-model').value) {
    $('#setup-model').value = data.models.includes(p?.suggested) ? p.suggested : (data.models[0] || '');
  }
  $('#setup-model-row').hidden = false;
  $('#setup-save').hidden = false;
  msg($('#setup-msg'), t('Conectado: {n} modelos disponibles. Elige uno y guarda.', { n: data.models.length }), 'ok');
};

$('#setup-save').onclick = async () => {
  msg($('#setup-msg'), t('Guardando y probando el modelo…'));
  const { ok, data } = await api('/api/providers/save', setupBody());
  if (!ok) return msg($('#setup-msg'), data.error || t('El modelo no respondió'), 'err');
  msg($('#setup-msg'), t('¡Listo! El modelo respondió: «{reply}»', { reply: data.reply }), 'ok');
  setTimeout(() => openPanel(null), 1200);
};

$('#mail-save').onclick = async () => {
  msg($('#mail-msg'), t('Conectando con tu correo…'));
  const { ok, data } = await api('/api/mail/save', {
    enabled: $('#mail-enabled').checked,
    user: $('#mail-user').value,
    password: $('#mail-pass').value,
    server: $('#mail-server').value,
  });
  $('#mail-pass').value = '';
  if (!ok) return msg($('#mail-msg'), data.error || t('No pude conectar'), 'err');
  msg($('#mail-msg'), data.server ? t('Conectado a {server} ({status})', { server: data.server, status: data.status }) : data.status, 'ok');
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
    loadMcp();
    loadAgentHooks();
    loadSpotify();
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
  if (version) $('#update-msg').textContent = t('Hay una versión nueva: {version}.', { version });
}

$('#update-btn').onclick = async () => {
  $('#update-btn').disabled = true;
  $('#update-msg').textContent = t('Descargando la actualización… Elissa se reiniciará sola.');
  try {
    await shell.installUpdate();
  } catch (e) {
    $('#update-btn').disabled = false;
    $('#update-msg').textContent = t('No se pudo actualizar: {error}', { error: e });
  }
};

shell.on('update-available', (version) => showUpdate(version));
shell.on('update-none', () => {
  openPanel('panel-settings');
  $('#update-row').hidden = false;
  $('#update-btn').hidden = true;
  $('#update-msg').textContent = t('Elissa está al día.');
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
  if (el.name === 'ui_language') {
    // speech follows the interface language: recognition language and a matching default voice
    const lang = resolveLang(value);
    const voice = lang === 'en' ? 'en-US-AvaNeural' : 'es-CO-SalomeNeural';
    $('#voice-select').innerHTML = '';
    saveSettings({ ui_language: value, language: lang === 'en' ? 'en-US' : 'es-CO', voice, language_autosynced: true })
      .then(loadVoices);
    return;
  }
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

/* ----- integrations (MCP) ----- */

let mcpPresets = [];

async function loadMcp() {
  const { data } = await api('/api/mcp');
  mcpPresets = data.presets || [];
  const sel = $('#mcp-preset');
  if (!sel.options.length) {
    sel.add(new Option(t('Elige un servicio…'), ''));
    for (const p of mcpPresets) sel.add(new Option(p.name, p.preset));
    sel.add(new Option(t('Otro servidor MCP…'), 'custom'));
  }
  const ul = $('#mcp-list');
  ul.innerHTML = '';
  for (const s of data.servers || []) {
    const on = el('input', { type: 'checkbox', checked: s.enabled !== false, title: t('Activado') });
    on.onchange = () => saveMcp({ server: { ...stripStatus(s), enabled: on.checked } });
    const rm = el('button', { type: 'button', textContent: '×', title: t('Quitar') });
    rm.onclick = async () => {
      await api('/api/mcp/remove', { id: s.id });
      loadMcp();
    };
    const cls = s.status.startsWith('conectado') ? 'st ok' : s.status.startsWith('error') ? 'st err' : 'st';
    ul.append(el('li', {}, on, el('span', { className: 'name', textContent: s.name }),
      el('span', { className: cls, textContent: s.status, title: s.status }), rm));
  }
}

async function loadSpotify() {
  const { data: s } = await api('/api/spotify');
  $('#spotify-redirect').textContent = s.redirect_uri;
  if (s.client_id && !$('#spotify-client').value) $('#spotify-client').value = s.client_id;
  $('#spotify-setup').hidden = s.connected;
  $('#spotify-connect').hidden = s.connected;
  $('#spotify-disconnect').hidden = !s.connected;
  $('#spotify-state').textContent = s.connected
    ? t('Conectado. Pídele «pon Soda Stereo» o «pon mi playlist de concentración».')
    : t('Conéctalo para que Elissa ponga canciones, artistas, álbumes y tus playlists.');
  $('#spotify-state').className = s.connected ? 'hint small ok' : 'hint small';
}

$('#spotify-connect').onclick = async () => {
  const r = await api('/api/spotify/connect', { client_id: $('#spotify-client').value.trim() });
  msg($('#spotify-msg'), r.ok ? t('Autoriza a Elissa en la página de Spotify que se abrió en tu navegador.') : r.data.error, r.ok ? '' : 'err');
};

$('#spotify-disconnect').onclick = async () => {
  await api('/api/spotify/disconnect', {});
  msg($('#spotify-msg'), t('Desconectado.'));
  loadSpotify();
};

async function loadAgentHooks() {
  const { data } = await api('/api/agent-hooks');
  const ul = $('#agents-list');
  ul.innerHTML = '';
  for (const [tool, s] of Object.entries(data)) {
    if (!s.label) continue;
    const btn = el('button', { type: 'button', textContent: s.installed ? t('Quitar') : t('Instalar') });
    btn.onclick = async () => {
      btn.disabled = true;
      const r = await api('/api/agent-hooks', { tool, on: !s.installed });
      const done = s.installed ? t('Quitado.') : tool === 'codex' ? t('Instalado. Al abrir Codex, apruébalo con /hooks.')
        : t('Instalado. Funciona en las sesiones nuevas de {tool}.', { tool: s.label });
      msg($('#agents-msg'), r.ok ? done : r.data.error || t('No se pudo.'), r.ok ? 'ok' : 'err');
      loadAgentHooks();
    };
    const status = s.installed ? t('activo') : s.detected ? t('no instalado') : t('no detectado');
    ul.append(el('li', {}, el('span', { className: 'name', textContent: s.label }),
      el('span', { className: s.installed ? 'st ok' : 'st', textContent: status, title: s.path }), btn));
  }
}

const AGENT_SAYS = {
  done: '{tool} terminó{where}.',
  permission: '{tool} necesita tu permiso{where}.',
  waiting: '{tool} te está esperando{where}.',
  error: '{tool} se detuvo por un error{where}.',
};

function announceAgent(m) {
  const where = m.project ? t(' en {project}', { project: m.project }) : '';
  const said = t(AGENT_SAYS[m.kind] || AGENT_SAYS.done, { tool: m.label, where });
  shell.notify(m.label, said);
  sfx.play(m.kind === 'error' ? 'error' : m.kind === 'done' ? 'done' : 'approval');
  face.play(m.kind === 'error' ? 'error' : m.kind === 'done' ? 'happy' : 'surprised', 900);
  const busy = ['listening', 'thinking', 'approval', 'speaking'].includes(state);
  if (busy || !cfg.agent_alerts_voice) {
    showCaption(undefined, said);
    return;
  }
  showCaption('', said);
  announcing = true;
  turnDone = true;
  enqueueSay(said);
}

function stripStatus(s) {
  const { status, tools, ...cfg } = s;
  return cfg;
}

async function saveMcp(body) {
  const { ok, data } = await api('/api/mcp/save', body);
  if (!ok) msg($('#mcp-msg'), data.error || t('No se pudo guardar'), 'err');
  loadMcp();
  return ok;
}

$('#mcp-preset').onchange = () => {
  const key = $('#mcp-preset').value;
  const p = mcpPresets.find((x) => x.preset === key);
  const custom = key === 'custom';
  $('#mcp-form').hidden = !key;
  $('#mcp-note').textContent = p?.note || (custom ? t('Usa solo servidores en los que confíes: pueden ejecutar programas en tu PC.') : '');
  for (const row of ['#mcp-name-row', '#mcp-transport-row']) $(row).hidden = !custom;
  const transport = custom ? $('#mcp-transport').value : p?.transport;
  $('#mcp-url-row').hidden = !custom || transport !== 'http';
  $('#mcp-command-row').hidden = !custom || transport !== 'stdio';
  $('#mcp-secret-row').hidden = !(custom || p?.secret);
  $('#mcp-secret-label').textContent = p?.secret?.label || t('Token (opcional, se envía como «Authorization: Bearer …»)');
  $('#mcp-help').hidden = !p?.secret?.help;
  if (p?.secret?.help) $('#mcp-help').href = p.secret.help;
  msg($('#mcp-msg'), '');
};
$('#mcp-transport').onchange = () => $('#mcp-preset').onchange();

$('#mcp-add').onclick = async () => {
  const key = $('#mcp-preset').value;
  const p = mcpPresets.find((x) => x.preset === key);
  const secret = $('#mcp-secret').value.trim();
  let server;
  const secrets = {};
  if (p) {
    server = { name: p.name, transport: p.transport, url: p.url, command: p.command, args: p.args, preset: p.preset,
      trust_reads: !!p.trust_reads };
    if (p.secret && secret) secrets[p.secret.key] = (p.secret.prefix || '') + secret;
    if (p.secret && !secret) return msg($('#mcp-msg'), t('Falta: {what}', { what: p.secret.label }), 'err');
  } else {
    const transport = $('#mcp-transport').value;
    const [command, ...args] = $('#mcp-command').value.trim().split(/\s+/);
    server = { name: $('#mcp-name').value.trim(), transport, url: $('#mcp-url').value.trim(), command, args,
      trust_reads: false };
    if (secret) secrets.Authorization = secret.startsWith('Bearer ') ? secret : `Bearer ${secret}`;
  }
  msg($('#mcp-msg'), t('Conectando…'));
  if (await saveMcp({ server, secrets })) {
    $('#mcp-secret').value = '';
    $('#mcp-preset').value = '';
    $('#mcp-form').hidden = true;
    msg($('#mcp-msg'), '');
  }
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
