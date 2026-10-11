// Elissa's character, drawn in code (no images) so every expression can blend smoothly into the next.
// Proportions come from design/ref/final-front.png, expressions from design/ref/final-expressions.png.
//
// Coordinates: the body lives in a 200×200 box (x 10–190, y 15–193); overlays (ears, waves, bubbles…) use the
// margin around it. Every visual property is a parameter that eases toward the target of the current expression.

const C = {
  body: '#33245c',
  outline: '#9be8ea',
  glow: '95, 227, 234',
  face: [242, 109, 91],
  faceHappy: [205, 247, 246],
  dark: '#2b1c4f',
  rim: '#c4f4f3',
  shine: '#f26d5b',
  cyan: '#7fe6ea',
  pink: '255, 150, 165',
  red: '#ff5a6a',
};

const VIEW = { x: -34, y: -44, w: 268, h: 266 }; // character space shown in the canvas
const SPRITE = { x: -30, y: -15, w: 260, h: 240 }; // area of the cached body + glow images
const EYES = [{ x: 69.5, y: 94 }, { x: 130.5, y: 94 }];
const EYE_R = 19;

// Target parameters per expression. Anything not listed falls back to BASE.
const BASE = {
  ears: 0, happy: 0, blush: 0, blushPink: 0, open: 1, pupil: 1, brow: 0, browL: 0, browR: 0, browY: 0,
  smile: 0.6, mouth: 0, mouthW: 12, glow: 0.45, lift: 0, gazeLock: 0, gazeX: 0, gazeY: 0, lid: 0, droop: 0,
};
const EXPRESSIONS = {
  idle: { eyes: 'round' },
  waking: { eyes: 'round', open: 0.55, smile: 0.3, glow: 0.25 },
  listening: { eyes: 'round', ears: 1, blush: 0.8, smile: 0.5, pupil: 1.08, overlay: 'waves2' },
  thinking: { eyes: 'round', brow: 1, browL: 0.12, browR: -0.38, browY: -2, smile: -0.35, gazeLock: 1, gazeX: 0.7,
    gazeY: -0.8, overlay: 'bubbles' },
  working: { eyes: 'round', lid: 0.25, smile: 0.25, overlay: 'gear' },
  speaking: { eyes: 'round', smile: 0.45, overlay: 'waves1' },
  happy: { eyes: 'happy', happy: 1, blush: 0.75, blushPink: 1, smile: 1, mouth: 0.45, glow: 1, lift: 1,
    overlay: 'sparkles' },
  approval: { eyes: 'round', brow: 1, browL: -0.32, browR: 0.32, browY: 1, smile: -0.45, pupil: 0.95,
    overlay: 'question' },
  error: { eyes: 'sad', brow: 1, browL: -0.34, browR: 0.34, browY: 2, blush: 0.5, blushPink: 1, smile: -0.75,
    overlay: 'exclaim' },
  sleeping: { eyes: 'closed', smile: 0, mouth: 0.18, mouthW: 4, glow: 0.18, overlay: 'zzz' },
  annoyed: { eyes: 'round', lid: 0.45, brow: 1, browL: 0.42, browR: -0.42, browY: 3, smile: -0.35, mouthW: 7 },
  dizzy: { eyes: 'spiral', mouth: 0.35, mouthW: 5, smile: 0, overlay: 'orbit' },
  love: { eyes: 'heart', blush: 0.8, blushPink: 1, smile: 0.85, mouth: 0.3, glow: 0.8, overlay: 'hearts' },
  surprised: { eyes: 'round', open: 1.12, pupil: 0.72, mouth: 0.5, mouthW: 6, smile: 0, brow: 1, browY: -6 },
};

const lerp = (a, b, t) => a + (b - a) * t;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

export class Character {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.levelSource = () => 0;
    this.expression = 'idle';
    this.p = { ...BASE };
    this.eyes = 'round';
    this.overlay = null;
    this.overlayT = 0;
    this.emote = null; // temporary expression on top of the state: { name, until }
    this.gaze = { x: 0, y: 0, tx: 0, ty: 0 };
    this.pointerAt = 0;
    this.blink = { next: performance.now() + 2500, start: 0 };
    this.nextGlance = performance.now() + 8000;
    this.bounce = 0; // poke squash
    this.t = 0;
    this.last = performance.now();
    this.frameMs = 1000 / 30;
    new ResizeObserver(() => this.resize()).observe(canvas);
    this.resize();
    document.addEventListener('visibilitychange', () => !document.hidden && this.kick());
    this.kick();
  }

  // ----- public API -----

  /** Base expression from the app state (idle, listening, thinking, speaking, error…). */
  setState(name) {
    this.expression = name in EXPRESSIONS ? name : 'idle';
    if (name === 'happy') this.bounce = -1;
    this.kick();
  }

  /** A short reaction on top of the state, e.g. 'love', 'annoyed', 'dizzy', 'surprised', 'happy'. */
  play(name, ms = 1600) {
    this.emote = { name, until: performance.now() + ms };
    if (name === 'annoyed' || name === 'dizzy') this.bounce = 1;
    if (name === 'happy') this.bounce = -1;
    this.kick();
  }

  /** Pointer position in window coordinates (CSS px), from page events or the global cursor. */
  lookAt(x, y) {
    const r = this.canvas.getBoundingClientRect();
    const eye = this.toScreen(100, EYES[0].y);
    const dx = x - (r.left + eye.x);
    const dy = y - (r.top + eye.y);
    const d = Math.hypot(dx, dy) || 1;
    const reach = d / (d + 70); // close to the face: small movement; far away: eyes at the edge
    this.gaze.tx = (dx / d) * reach;
    this.gaze.ty = (dy / d) * reach;
    this.pointerAt = performance.now();
    this.kick();
  }

  // ----- loop -----

  /**
   * Starts the render loop if it is stopped. At rest nothing is redrawn (a transparent always-on-top window costs
   * CPU on every frame): the loop runs while something moves and then sleeps until the next blink or glance.
   */
  kick() {
    clearTimeout(this.wakeTimer);
    if (this.running) return;
    this.running = true;
    this.last = performance.now();
    const step = (now) => {
      if (document.hidden) {
        this.running = false;
        return;
      }
      if (now - this.last >= this.frameMs - 2) {
        const dt = Math.min(0.1, (now - this.last) / 1000);
        this.last = now;
        this.update(dt, now);
        this.draw();
        if (!this.animating) {
          this.running = false;
          const wait = Math.max(50, Math.min(this.blink.next, this.nextGlance, now + 5000) - now);
          this.wakeTimer = setTimeout(() => this.kick(), wait);
          return;
        }
      }
      requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  resize() {
    const d = window.devicePixelRatio || 1;
    const { clientWidth: w, clientHeight: h } = this.canvas;
    this.canvas.width = Math.max(1, Math.round(w * d));
    this.canvas.height = Math.max(1, Math.round(h * d));
    const s = Math.min(w / VIEW.w, h / VIEW.h);
    this.scale = s;
    this.ox = (w - VIEW.w * s) / 2 - VIEW.x * s;
    this.oy = h - VIEW.h * s - VIEW.y * s - (h - VIEW.h * s) * 0.15;
    this.dpr = d;
    this.sprites = null; // rebuilt at the new resolution on the next frame
  }

  /** The body never changes shape, so it and its glow (a costly blur) are drawn once into images. */
  buildSprites() {
    const px = this.scale * this.dpr;
    const make = (paint) => {
      const c = document.createElement('canvas');
      c.width = Math.ceil(SPRITE.w * px);
      c.height = Math.ceil(SPRITE.h * px);
      const g = c.getContext('2d');
      g.setTransform(px, 0, 0, px, -SPRITE.x * px, -SPRITE.y * px);
      paint(g);
      return c;
    };
    const path = this.bodyPath();
    const glow = make((g) => {
      g.shadowColor = `rgba(${C.glow}, 0.9)`;
      g.shadowBlur = 30 * px;
      g.fillStyle = C.body;
      g.fill(path);
      g.fill(path); // twice: a stronger halo
    });
    const body = make((g) => {
      g.fillStyle = C.body;
      g.fill(path);
      g.lineWidth = 5.5;
      g.strokeStyle = C.outline;
      g.stroke(path);
      g.lineCap = 'round';
      g.strokeStyle = C.shine;
      g.lineWidth = 3.4;
      g.beginPath();
      g.moveTo(25, 123);
      g.quadraticCurveTo(27, 160, 47, 176);
      g.stroke();
      g.beginPath();
      g.moveTo(129, 175);
      g.lineTo(139, 168);
      g.stroke();
    });
    this.sprites = { glow, body };
  }

  toScreen(x, y) {
    return { x: this.ox + x * this.scale, y: this.oy + y * this.scale };
  }

  current() {
    if (this.emote && performance.now() < this.emote.until) return this.emote.name;
    this.emote = null;
    return this.expression;
  }

  update(dt, now) {
    this.t += dt;
    const name = this.current();
    const target = { ...BASE, ...EXPRESSIONS[name] };
    const level = clamp(this.levelSource() || 0, 0, 1);
    if (name === 'speaking') target.mouth = 0.12 + level * 0.75;
    if (name === 'listening') target.glow = 0.45 + level * 0.55;

    // Eye style and overlay switch instantly, hidden by a quick blink.
    if (target.eyes !== this.eyes) {
      this.eyes = target.eyes;
      this.blink.start = now;
    }
    if ((target.overlay || null) !== this.overlay) {
      this.overlay = target.overlay || null;
      this.overlayT = 0;
    }
    this.overlayT += dt;

    const k = 1 - Math.exp(-dt * 9);
    let settling = false;
    for (const key of Object.keys(BASE)) {
      const v = lerp(this.p[key], target[key], k);
      if (Math.abs(v - target[key]) > 0.002) settling = true;
      this.p[key] = Math.abs(v - target[key]) > 0.002 ? v : target[key];
    }

    // Gaze: follow the pointer; glance around now and then when it has been still for a while.
    if (this.p.gazeLock > 0.5) {
      this.gaze.tx = target.gazeX;
      this.gaze.ty = target.gazeY;
    } else if (now - this.pointerAt > 6000 && now > this.nextGlance) {
      this.gaze.tx = (Math.random() * 2 - 1) * 0.7;
      this.gaze.ty = (Math.random() * 2 - 1) * 0.4;
      this.nextGlance = now + 3500 + Math.random() * 6000;
    }
    const g = 1 - Math.exp(-dt * 14);
    this.gaze.x = lerp(this.gaze.x, this.gaze.tx, g);
    this.gaze.y = lerp(this.gaze.y, this.gaze.ty, g);

    // Blinks every few seconds (sometimes twice); none while asleep or with special eyes.
    if (now > this.blink.next) {
      this.blink.start = now;
      this.blink.next = now + 2200 + Math.random() * 4200;
      if (Math.random() < 0.18) this.blink.double = now + 260;
    }
    if (this.blink.double && now > this.blink.double) {
      this.blink.start = now;
      this.blink.double = 0;
    }

    this.bounce = lerp(this.bounce, 0, 1 - Math.exp(-dt * 6));
    const busy = name !== 'idle' && name !== 'sleeping' && name !== 'waking';
    const moving = Math.abs(this.gaze.tx - this.gaze.x) > 0.005 || Math.abs(this.gaze.ty - this.gaze.y) > 0.005
      || now - this.blink.start < 200 || Math.abs(this.bounce) > 0.02 || settling;
    // Busy states breathe and animate their effects; sleep breathes slowly; idle only moves when something happens.
    this.animating = busy || !!this.emote || moving || name === 'sleeping' || this.overlayT < 0.3;
    this.breathing = busy || name === 'sleeping';
    this.frameMs = 1000 / (busy || this.emote || moving ? 60 : 8);
  }

  blinkAmount(now) {
    const ms = now - this.blink.start;
    if (ms < 0 || ms > 160) return 1;
    return Math.abs(ms - 80) / 80; // 1 → 0 → 1
  }

  // ----- drawing -----

  draw() {
    const { ctx, p } = this;
    const now = performance.now();
    const w = this.canvas.width;
    const h = this.canvas.height;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.setTransform(this.dpr * this.scale, 0, 0, this.dpr * this.scale, this.dpr * this.ox, this.dpr * this.oy);

    const name = this.current();
    const sleeping = name === 'sleeping';
    const breath = this.breathing ? Math.sin(this.t * (sleeping ? 1.4 : 2.4)) : 0;
    const lift = p.lift * Math.abs(Math.sin(this.t * 7)) * -7; // happy hop
    const sy = 1 + breath * (sleeping ? 0.025 : 0.014) - this.bounce * 0.06;
    const sx = 1 - breath * 0.008 + this.bounce * 0.05;
    const tilt = this.gaze.x * 0.035 + (name === 'dizzy' ? Math.sin(this.t * 5) * 0.08 : 0);

    ctx.save();
    ctx.translate(100, 193 + lift);
    ctx.rotate(tilt);
    ctx.scale(sx, sy);
    ctx.translate(-100, -193);

    this.drawEars();
    this.drawBody();
    this.drawFace(now);
    ctx.restore();

    this.drawOverlay(lift);
  }

  bodyPath() {
    const path = new Path2D();
    // A round dome that bulges at the sides, sitting on two little feet.
    path.moveTo(100, 16);
    path.bezierCurveTo(158, 16, 194, 58, 193, 112);
    path.bezierCurveTo(192, 148, 190, 172, 182, 185);
    path.bezierCurveTo(175, 196, 142, 197, 127, 193);
    path.bezierCurveTo(119, 191, 117, 175, 100, 175);
    path.bezierCurveTo(83, 175, 81, 191, 73, 193);
    path.bezierCurveTo(58, 197, 25, 196, 18, 185);
    path.bezierCurveTo(10, 172, 8, 148, 7, 112);
    path.bezierCurveTo(6, 58, 42, 16, 100, 16);
    path.closePath();
    return path;
  }

  drawEars() {
    const e = this.p.ears;
    if (e < 0.02) return;
    const { ctx } = this;
    const wiggle = Math.sin(this.t * 9) * 0.06 * e;
    for (const side of [-1, 1]) {
      ctx.save();
      ctx.translate(100 + side * 34, 30);
      ctx.rotate(side * (0.28 + wiggle));
      ctx.beginPath();
      // a soft rounded ear that pops up out of the head
      ctx.moveTo(-7, 4);
      ctx.bezierCurveTo(-10, -16 * e, -7, -34 * e, 0, -34 * e);
      ctx.bezierCurveTo(7, -34 * e, 10, -16 * e, 7, 4);
      ctx.closePath();
      ctx.fillStyle = C.shine;
      ctx.fill();
      ctx.restore();
    }
  }

  drawBody() {
    const { ctx, p } = this;
    if (!this.sprites) this.buildSprites();
    ctx.save();
    ctx.globalAlpha = clamp(0.25 + p.glow * 0.75, 0, 1);
    ctx.drawImage(this.sprites.glow, SPRITE.x, SPRITE.y, SPRITE.w, SPRITE.h);
    ctx.restore();
    ctx.drawImage(this.sprites.body, SPRITE.x, SPRITE.y, SPRITE.w, SPRITE.h);
  }

  drawFace(now) {
    const { ctx, p } = this;
    const px = this.gaze.x * 3;
    const py = this.gaze.y * 2.5;
    // face disc
    const f = C.face.map((c, i) => Math.round(lerp(c, C.faceHappy[i], p.happy)));
    ctx.beginPath();
    ctx.ellipse(100 + px, 97 + py, 67, 57, 0, 0, Math.PI * 2);
    ctx.fillStyle = `rgb(${f.join(',')})`;
    ctx.fill();
    if (p.happy > 0.05) {
      ctx.fillStyle = `rgba(255,255,255,${0.35 * p.happy})`;
      ctx.beginPath();
      ctx.ellipse(118 + px, 62 + py, 14, 6, -0.3, 0, Math.PI * 2);
      ctx.fill();
    }
    // blush
    if (p.blush > 0.02) {
      const tint = p.blushPink > 0.5 ? `rgba(${C.pink}, ${0.55 * p.blush})` : `rgba(127, 230, 234, ${0.7 * p.blush})`;
      ctx.fillStyle = tint;
      for (const e of EYES) {
        ctx.beginPath();
        ctx.ellipse(e.x + px + (e.x < 100 ? -4 : 4), 120 + py, 11, 6, 0, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    const open = clamp(p.open * this.blinkAmount(now), 0, 1.2);
    EYES.forEach((e, i) => this.drawEye(e.x + px, e.y + py, open, i));
    this.drawBrows(px, py);
    this.drawMouth(100 + px, 118 + py);
  }

  drawEye(x, y, open, i) {
    const { ctx, p } = this;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = C.dark;
    ctx.fillStyle = C.dark;
    const style = this.eyes;
    if (style === 'happy' || (style === 'round' && open < 0.12)) {
      ctx.lineWidth = 4;
      ctx.beginPath();
      if (style === 'happy') ctx.arc(x, y + 4, 11, Math.PI * 1.1, Math.PI * 1.9);
      else { ctx.moveTo(x - 13, y); ctx.lineTo(x + 13, y); }
      ctx.stroke();
      return;
    }
    if (style === 'closed') {
      ctx.lineWidth = 3.6;
      ctx.beginPath();
      ctx.arc(x, y - 6, 13, Math.PI * 0.2, Math.PI * 0.8);
      ctx.stroke();
      return;
    }
    if (style === 'spiral') {
      ctx.lineWidth = 2.6;
      ctx.beginPath();
      const spin = this.t * 6 * (i ? -1 : 1);
      for (let a = 0; a < Math.PI * 6; a += 0.2) {
        const r = 1 + a * 0.85;
        const xx = x + Math.cos(a + spin) * r;
        const yy = y + Math.sin(a + spin) * r;
        a === 0 ? ctx.moveTo(xx, yy) : ctx.lineTo(xx, yy);
      }
      ctx.stroke();
      return;
    }
    if (style === 'heart') {
      const s = 1 + Math.sin(this.t * 8) * 0.08;
      ctx.save();
      ctx.translate(x, y);
      ctx.scale(s, s);
      heart(ctx, 0, -2, 15);
      ctx.fill();
      ctx.fillStyle = C.rim;
      ctx.beginPath();
      ctx.arc(-5, -6, 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
      return;
    }
    // round (also sad): pale rim, dark pupil following the gaze, highlight
    const ry = EYE_R * open;
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(x, y, EYE_R, ry, 0, 0, Math.PI * 2);
    ctx.fillStyle = C.rim;
    ctx.fill();
    ctx.clip();
    const gx = this.gaze.x * 5;
    const gy = this.gaze.y * 4.5;
    const pr = 14.5 * p.pupil;
    ctx.fillStyle = C.dark;
    ctx.beginPath();
    ctx.arc(x + gx, y + gy + 1, pr, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = C.rim;
    ctx.beginPath();
    ctx.arc(x + gx + 4.5, y + gy - 4.5, style === 'sad' ? 5 : 3.8, 0, Math.PI * 2);
    ctx.fill();
    if (style === 'sad') {
      ctx.beginPath();
      ctx.arc(x + gx - 4, y + gy + 6, 2.2, 0, Math.PI * 2);
      ctx.fill();
    }
    // eyelids: annoyed/working half-lid, sad droop toward the outside
    const lid = Math.max(p.lid, style === 'sad' ? 0.3 : 0);
    if (lid > 0.02) {
      const f = C.face.map((c, k) => Math.round(lerp(c, C.faceHappy[k], p.happy)));
      ctx.fillStyle = `rgb(${f.join(',')})`;
      const out = i === 0 ? -1 : 1;
      const tiltLid = style === 'sad' ? 7 * out : 0;
      ctx.beginPath();
      ctx.moveTo(x - 24, y - 24);
      ctx.lineTo(x + 24, y - 24);
      ctx.lineTo(x + 24, y - EYE_R + lid * 2 * EYE_R + tiltLid);
      ctx.lineTo(x - 24, y - EYE_R + lid * 2 * EYE_R - tiltLid);
      ctx.closePath();
      ctx.fill();
    }
    ctx.restore();
  }

  drawBrows(px, py) {
    const { ctx, p } = this;
    if (p.brow < 0.03) return;
    ctx.save();
    ctx.globalAlpha = clamp(p.brow, 0, 1);
    ctx.strokeStyle = C.dark;
    ctx.lineWidth = 3.4;
    ctx.lineCap = 'round';
    EYES.forEach((e, i) => {
      const a = i === 0 ? p.browL : p.browR;
      ctx.save();
      ctx.translate(e.x + px, e.y - 27 + p.browY + py);
      ctx.rotate(a);
      ctx.beginPath();
      ctx.moveTo(-9, 0);
      ctx.quadraticCurveTo(0, -3, 9, 0);
      ctx.stroke();
      ctx.restore();
    });
    ctx.restore();
  }

  drawMouth(x, y) {
    const { ctx, p } = this;
    const w = p.mouthW;
    ctx.strokeStyle = C.dark;
    ctx.fillStyle = C.dark;
    ctx.lineWidth = 3.6;
    ctx.lineCap = 'round';
    const curve = p.smile * 9;
    if (p.mouth < 0.06) {
      ctx.beginPath();
      ctx.moveTo(x - w, y - curve * 0.25);
      ctx.quadraticCurveTo(x, y + curve, x + w, y - curve * 0.25);
      ctx.stroke();
      return;
    }
    const top = y - curve * 0.15;
    const depth = 3 + p.mouth * 13;
    ctx.beginPath();
    ctx.moveTo(x - w, top);
    ctx.quadraticCurveTo(x, top + curve * 0.5, x + w, top);
    ctx.quadraticCurveTo(x + w * 0.9, top + depth, x, top + depth + curve * 0.2);
    ctx.quadraticCurveTo(x - w * 0.9, top + depth, x - w, top);
    ctx.closePath();
    ctx.fill();
    if (p.mouth > 0.25) {
      ctx.save();
      ctx.clip();
      ctx.fillStyle = '#ff8e86';
      ctx.beginPath();
      ctx.ellipse(x, top + depth + 2, w * 0.55, depth * 0.45, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
  }

  drawOverlay(lift) {
    const { ctx } = this;
    const t = this.overlayT;
    const fade = clamp(t * 4, 0, 1);
    if (!this.overlay || fade <= 0) return;
    ctx.save();
    ctx.globalAlpha = fade;
    ctx.lineCap = 'round';
    // a soft dark halo keeps light effects readable on light wallpapers
    ctx.shadowColor = 'rgba(30, 20, 60, 0.6)';
    ctx.shadowBlur = 3 * this.scale * this.dpr;
    switch (this.overlay) {
      case 'waves2':
      case 'waves1': {
        const level = clamp(this.levelSource() || 0, 0, 1);
        const sides = this.overlay === 'waves2' ? [-1, 1] : [1];
        ctx.strokeStyle = C.cyan;
        ctx.lineWidth = 3.2;
        for (const side of sides) {
          for (let k = 0; k < 3; k++) {
            const phase = (this.t * 1.6 + k / 3) % 1;
            ctx.globalAlpha = fade * (1 - phase) * (0.45 + level * 0.55);
            ctx.beginPath();
            const cx = side > 0 ? 194 : 6;
            ctx.arc(cx, 96, 8 + phase * 22, side > 0 ? -0.7 : Math.PI - 0.7, side > 0 ? 0.7 : Math.PI + 0.7);
            ctx.stroke();
          }
        }
        break;
      }
      case 'bubbles': {
        ctx.fillStyle = C.cyan;
        [[168, 6, 4.5], [182, -10, 6.5], [200, -28, 9.5]].forEach(([x, y, r], i) => {
          const bob = Math.sin(this.t * 2.2 + i) * 2.5;
          ctx.globalAlpha = fade * clamp((t - i * 0.25) * 3, 0, 1);
          ctx.beginPath();
          ctx.arc(x, y + bob, r, 0, Math.PI * 2);
          ctx.fill();
        });
        break;
      }
      case 'sparkles': {
        ctx.fillStyle = '#ffffff';
        [[182, 0 + lift, 9, 0], [200, 26 + lift, 6, 1.7]].forEach(([x, y, r, ph]) => {
          star4(ctx, x, y, r * (0.75 + 0.25 * Math.sin(this.t * 6 + ph)));
          ctx.fill();
        });
        break;
      }
      case 'question':
      case 'exclaim': {
        const bob = Math.sin(this.t * 3) * 3;
        ctx.fillStyle = this.overlay === 'question' ? C.cyan : C.red;
        ctx.font = 'bold 34px "Segoe UI", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(this.overlay === 'question' ? '?' : '!', 190, 6 + bob);
        break;
      }
      case 'zzz': {
        ctx.fillStyle = C.rim;
        ctx.textAlign = 'center';
        for (let k = 0; k < 2; k++) {
          const ph = (this.t * 0.35 + k * 0.5) % 1;
          ctx.globalAlpha = fade * Math.sin(ph * Math.PI);
          ctx.font = `bold ${14 + ph * 14}px "Segoe UI", sans-serif`;
          ctx.fillText(k ? 'Z' : 'z', 172 + ph * 26, 12 - ph * 34);
        }
        break;
      }
      case 'orbit': {
        ctx.strokeStyle = C.cyan;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.ellipse(100, 14, 82, 13, 0, 0, Math.PI * 2);
        ctx.stroke();
        for (let k = 0; k < 3; k++) {
          const a = this.t * 3 + (k * Math.PI * 2) / 3;
          ctx.fillStyle = k % 2 ? C.shine : C.cyan;
          star5(ctx, 100 + Math.cos(a) * 82, 14 + Math.sin(a) * 13, 7);
          ctx.fill();
        }
        break;
      }
      case 'hearts': {
        ctx.fillStyle = C.shine;
        [[-8, 0], [196, 0.45], [186, 0.8]].forEach(([x, off]) => {
          const ph = (this.t * 0.45 + off) % 1;
          ctx.globalAlpha = fade * Math.sin(ph * Math.PI);
          heart(ctx, x, 40 - ph * 60, 9 + ph * 5);
          ctx.fill();
        });
        break;
      }
      case 'gear': {
        ctx.fillStyle = C.shine;
        gear(ctx, 190, -6, 11, this.t * 2.5);
        break;
      }
    }
    ctx.restore();
  }
}

// ----- shapes -----

function heart(ctx, x, y, s) {
  ctx.beginPath();
  ctx.moveTo(x, y + s * 0.75);
  ctx.bezierCurveTo(x - s * 1.25, y - s * 0.05, x - s * 0.55, y - s * 0.95, x, y - s * 0.35);
  ctx.bezierCurveTo(x + s * 0.55, y - s * 0.95, x + s * 1.25, y - s * 0.05, x, y + s * 0.75);
  ctx.closePath();
}

function star4(ctx, x, y, r) {
  ctx.beginPath();
  for (let i = 0; i < 8; i++) {
    const a = (i * Math.PI) / 4 - Math.PI / 2;
    const rr = i % 2 ? r * 0.28 : r;
    ctx.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr);
  }
  ctx.closePath();
}

function star5(ctx, x, y, r) {
  ctx.beginPath();
  for (let i = 0; i < 10; i++) {
    const a = (i * Math.PI) / 5 - Math.PI / 2;
    const rr = i % 2 ? r * 0.45 : r;
    ctx.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr);
  }
  ctx.closePath();
}

function gear(ctx, x, y, r, a) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(a);
  ctx.beginPath();
  for (let i = 0; i < 16; i++) {
    const ang = (i * Math.PI) / 8;
    const rr = i % 2 ? r : r * 1.35;
    ctx.lineTo(Math.cos(ang - 0.18) * rr, Math.sin(ang - 0.18) * rr);
    ctx.lineTo(Math.cos(ang + 0.18) * rr, Math.sin(ang + 0.18) * rr);
  }
  ctx.closePath();
  ctx.fill();
  ctx.globalCompositeOperation = 'destination-out';
  ctx.beginPath();
  ctx.arc(0, 0, r * 0.42, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}
