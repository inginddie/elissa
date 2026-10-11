// Elissa's sounds, synthesized with Web Audio (no files, nothing to license). Any of them can be replaced by
// dropping e.g. `listen.wav` or `done.mp3` in the sounds folder (Settings → Sounds → Open folder).

export const SOUND_NAMES = [
  'greet', 'listen', 'stop', 'send', 'done', 'error', 'approval', 'poke', 'annoyed', 'dizzy', 'love', 'happy',
  'sleep', 'wake', 'open', 'close', 'drag', 'tick',
];

export class Sounds {
  constructor(getContext) {
    this.getContext = getContext; // the app's shared AudioContext (created after the first gesture/auto-play)
    this.volume = 0.6;
    this.enabled = true;
    this.custom = new Map(); // name -> AudioBuffer from the user's sounds folder
    this.lastPlayed = new Map();
  }

  /** Loads the user's replacement sounds listed by the engine. */
  async loadCustom(list) {
    const ctx = this.getContext();
    if (!ctx) return;
    this.custom.clear();
    for (const { name, url } of list || []) {
      try {
        const buf = await (await fetch(url)).arrayBuffer();
        this.custom.set(name, await ctx.decodeAudioData(buf));
      } catch {
        // an unreadable file just keeps the built-in sound
      }
    }
  }

  play(name) {
    const ctx = this.getContext();
    if (!ctx || !this.enabled || this.volume <= 0) return;
    const now = performance.now();
    if (now - (this.lastPlayed.get(name) || 0) < 80) return; // no machine-gun repeats
    this.lastPlayed.set(name, now);
    const out = ctx.createGain();
    out.gain.value = this.volume;
    out.connect(ctx.destination);
    const custom = this.custom.get(name);
    if (custom) {
      const src = ctx.createBufferSource();
      src.buffer = custom;
      src.connect(out);
      src.start();
      return;
    }
    const recipe = RECIPES[name];
    if (recipe) recipe(new Synth(ctx, out));
  }
}

class Synth {
  constructor(ctx, out) {
    this.ctx = ctx;
    this.out = out;
    this.t0 = ctx.currentTime + 0.005;
  }

  /** A pitched blip: frequency (optionally gliding), soft attack, exponential decay. */
  tone(at, freq, dur, { type = 'sine', to = freq, gain = 0.25, attack = 0.008, vibrato = 0 } = {}) {
    const { ctx } = this;
    const t = this.t0 + at;
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = type;
    o.frequency.setValueAtTime(freq, t);
    if (to !== freq) o.frequency.exponentialRampToValueAtTime(to, t + dur);
    if (vibrato) {
      const lfo = ctx.createOscillator();
      const depth = ctx.createGain();
      lfo.frequency.value = vibrato;
      depth.gain.value = freq * 0.06;
      lfo.connect(depth).connect(o.frequency);
      lfo.start(t);
      lfo.stop(t + dur + 0.05);
    }
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(gain, t + attack);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g).connect(this.out);
    o.start(t);
    o.stop(t + dur + 0.05);
  }

  /** Filtered noise burst (whooshes, taps). */
  noise(at, dur, { freq = 1200, q = 0.8, gain = 0.15, type = 'bandpass', to = freq } = {}) {
    const { ctx } = this;
    const t = this.t0 + at;
    const len = Math.ceil(ctx.sampleRate * dur);
    const buf = ctx.createBuffer(1, len, ctx.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < len; i++) data[i] = Math.random() * 2 - 1;
    const src = ctx.createBufferSource();
    src.buffer = buf;
    const f = ctx.createBiquadFilter();
    f.type = type;
    f.Q.value = q;
    f.frequency.setValueAtTime(freq, t);
    if (to !== freq) f.frequency.exponentialRampToValueAtTime(to, t + dur);
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(gain, t + dur * 0.15);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    src.connect(f).connect(g).connect(this.out);
    src.start(t);
    src.stop(t + dur + 0.02);
  }
}

// Musical-ish palette around A major / F# minor so everything sounds like the same character.
const RECIPES = {
  greet: (s) => {
    [659, 880, 1109, 1319].forEach((f, i) => s.tone(i * 0.085, f, 0.22, { type: 'triangle', gain: 0.18 }));
    s.tone(0.36, 1760, 0.35, { gain: 0.08 });
  },
  listen: (s) => {
    s.tone(0, 587, 0.12, { to: 880, type: 'triangle', gain: 0.22 });
    s.tone(0.08, 1175, 0.16, { gain: 0.12 });
  },
  stop: (s) => s.tone(0, 880, 0.16, { to: 523, type: 'triangle', gain: 0.18 }),
  send: (s) => {
    s.noise(0, 0.18, { freq: 900, to: 3800, gain: 0.07 });
    s.tone(0.05, 988, 0.12, { to: 1319, gain: 0.12 });
  },
  done: (s) => {
    s.tone(0, 880, 0.3, { gain: 0.14 });
    s.tone(0.1, 1109, 0.3, { gain: 0.12 });
    s.tone(0.2, 1319, 0.45, { gain: 0.12 });
  },
  error: (s) => {
    s.tone(0, 392, 0.2, { type: 'triangle', gain: 0.2 });
    s.tone(0.17, 311, 0.32, { type: 'triangle', to: 277, gain: 0.2 });
  },
  approval: (s) => {
    s.tone(0, 1319, 0.16, { gain: 0.18 });
    s.tone(0.2, 1319, 0.16, { gain: 0.18 });
    s.tone(0.2, 1760, 0.22, { gain: 0.08 });
  },
  poke: (s) => s.tone(0, 330, 0.22, { to: 520, type: 'sine', gain: 0.3, vibrato: 18 }),
  annoyed: (s) => {
    s.tone(0, 220, 0.14, { type: 'sawtooth', to: 196, gain: 0.07 });
    s.tone(0.13, 233, 0.2, { type: 'sawtooth', to: 175, gain: 0.07 });
  },
  dizzy: (s) => s.tone(0, 1200, 0.9, { to: 300, type: 'triangle', gain: 0.16, vibrato: 9 }),
  love: (s) => {
    s.tone(0, 1568, 0.35, { gain: 0.12 });
    s.tone(0.14, 2093, 0.45, { gain: 0.1 });
  },
  happy: (s) => [880, 1109, 1319, 1760].forEach((f, i) => s.tone(i * 0.05, f, 0.18, { gain: 0.1 })),
  sleep: (s) => s.tone(0, 660, 0.9, { to: 330, type: 'triangle', gain: 0.1, attack: 0.08 }),
  wake: (s) => s.tone(0, 440, 0.25, { to: 880, type: 'triangle', gain: 0.14 }),
  open: (s) => s.tone(0, 740, 0.07, { to: 988, gain: 0.1 }),
  close: (s) => s.tone(0, 988, 0.07, { to: 740, gain: 0.1 }),
  drag: (s) => s.noise(0, 0.25, { freq: 600, to: 2400, gain: 0.06 }),
  tick: (s) => s.tone(0, 2200, 0.03, { gain: 0.05 }),
};
