"""« Hola Elissa »: an optional, fully local wake phrase.

A background thread reads the microphone (16 kHz mono) and, only while someone is speaking (a simple energy
detector), feeds the audio to Vosk restricted to a tiny grammar: the wake phrases plus look-alike decoys ("hola
Melisa", "es Elisa"…) so that similar speech lands on a decoy instead of waking her up. Nothing leaves the PC.

It pauses while Elissa herself is listening or speaking, and while the session is locked (the microphone is
closed then). The Vosk model (~40 MB) is downloaded once, verified with SHA-256.
"""
import array
import ctypes
import hashlib
import json
import logging
import math
import queue
import shutil
import threading
import time
import zipfile
from pathlib import Path
from typing import Callable

import httpx

log = logging.getLogger(__name__)

MODEL_NAME = "vosk-model-small-es-0.42"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"
MODEL_SHA256 = "09b239888f633ef2f0b4e09736e3d9936acfd810bc65d53fad45261762c6511f"

RATE = 16000
BLOCK = 1600  # 100 ms
PREROLL_BLOCKS = 4  # keep 400 ms before the speech starts
END_SILENCE_BLOCKS = 7  # 700 ms of silence ends an utterance
MAX_UTTERANCE_BLOCKS = 40  # 4 s: wake phrases are short
COOLDOWN_S = 2.5

WAKE = ("hola elisa", "oye elisa")
# No "hola lisa" decoy: said quickly, "hola Elissa" merges into exactly that.
GRAMMAR = list(WAKE) + ["hola melisa", "hola luisa", "hola alicia", "hola elena", "es elisa", "la elisa",
                        "a elisa", "de elisa", "con elisa", "y elisa", "ella es", "hola", "elisa", "[unk]"]


def is_wake(text: str) -> bool:
    return text.strip().startswith(WAKE)


def _rms(block: bytes) -> float:
    samples = array.array("h", block)
    if not samples:
        return 0.0
    return math.sqrt(sum(s * s for s in samples) / len(samples)) / 32768


def session_locked() -> bool:
    """True while the Windows session is locked (the input desktop can't be opened)."""
    user32 = ctypes.windll.user32
    desk = user32.OpenInputDesktop(0, False, 0x0100)  # DESKTOP_SWITCHDESKTOP
    if not desk:
        return True
    try:
        return not user32.SwitchDesktop(desk)
    finally:
        user32.CloseDesktop(desk)


class WakeListener:
    def __init__(self, models_dir: Path, on_wake: Callable[[], None], on_status: Callable[[str], None]):
        self.models_dir = models_dir
        self.on_wake = on_wake
        self.on_status = on_status
        self.enabled = False
        self.busy = False  # Elissa is listening or speaking herself
        self.status = "apagado"
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._download_lock = threading.Lock()

    @property
    def model_path(self) -> Path:
        return self.models_dir / MODEL_NAME

    def _set_status(self, status: str) -> None:
        if status != self.status:
            self.status = status
            self.on_status(status)

    # ----- model -----

    def ensure_model(self, progress: Callable[[int], None] = lambda pct: None) -> Path:
        with self._download_lock:
            if (self.model_path / "am").exists():
                return self.model_path
            self.models_dir.mkdir(parents=True, exist_ok=True)
            tmp = self.models_dir / f"{MODEL_NAME}.zip.part"
            digest = hashlib.sha256()
            with httpx.stream("GET", MODEL_URL, follow_redirects=True, timeout=60) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length") or 0)
                done = 0
                with open(tmp, "wb") as f:
                    for chunk in r.iter_bytes(1 << 16):
                        f.write(chunk)
                        digest.update(chunk)
                        done += len(chunk)
                        if total:
                            progress(done * 100 // total)
            if digest.hexdigest() != MODEL_SHA256:
                tmp.unlink(missing_ok=True)
                raise RuntimeError("El modelo descargado no coincide con el esperado; no lo usé.")
            staging = self.models_dir / f"{MODEL_NAME}.staging"
            shutil.rmtree(staging, ignore_errors=True)
            with zipfile.ZipFile(tmp) as z:
                for member in z.namelist():  # no path tricks inside the archive
                    if member.startswith("/") or ".." in Path(member).parts:
                        raise RuntimeError("El archivo del modelo no es válido.")
                z.extractall(staging)
            shutil.rmtree(self.model_path, ignore_errors=True)
            (staging / MODEL_NAME).rename(self.model_path)
            shutil.rmtree(staging, ignore_errors=True)
            tmp.unlink(missing_ok=True)
            return self.model_path

    # ----- lifecycle -----

    def set_enabled(self, on: bool) -> None:
        self.enabled = on
        if on and not (self._thread and self._thread.is_alive()):
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="wake", daemon=True)
            self._thread.start()
        elif not on:
            self._stop.set()
            self._set_status("apagado")

    def _run(self) -> None:
        try:
            if not (self.model_path / "am").exists():
                self._set_status("descargando 0%")
                self.ensure_model(lambda pct: self._set_status(f"descargando {pct}%"))
            import vosk
            vosk.SetLogLevel(-1)
            model = vosk.Model(str(self.model_path))
        except Exception as e:
            log.exception("wake word unavailable")
            self._set_status(f"error: {e}")
            return
        while not self._stop.is_set():
            if session_locked():
                self._set_status("en pausa (pantalla bloqueada)")
                self._stop.wait(2)
                continue
            try:
                self._listen(model)
            except Exception as e:  # microphone unplugged or busy: retry in a moment
                log.warning("wake listener: %s", e)
                self._set_status("sin micrófono, reintentando…")
                self._stop.wait(3)

    def _listen(self, model) -> None:
        import sounddevice as sd
        blocks: queue.Queue[bytes] = queue.Queue(maxsize=50)

        def callback(data, frames, time_info, status):
            try:
                blocks.put_nowait(bytes(data))
            except queue.Full:
                pass

        spotter = Spotter(model)
        with sd.RawInputStream(samplerate=RATE, blocksize=BLOCK, channels=1, dtype="int16", callback=callback):
            self._set_status("escuchando «Hola Elissa»")
            last_lock_check = time.monotonic()
            while not self._stop.is_set():
                if time.monotonic() - last_lock_check > 2:
                    last_lock_check = time.monotonic()
                    if session_locked():
                        return  # closes the microphone; _run waits for the unlock
                try:
                    block = blocks.get(timeout=0.5)
                except queue.Empty:
                    continue
                if self.busy:
                    spotter.reset()
                    continue
                if spotter.feed(block):
                    log.info("wake phrase heard")
                    self.on_wake()


class Spotter:
    """Turns 100 ms blocks of 16 kHz audio into wake events: energy gate → Vosk with the wake grammar."""

    def __init__(self, model):
        import vosk
        self._vosk = vosk
        self.model = model
        self.grammar = json.dumps(GRAMMAR)
        self.noise = 0.004
        self.cooldown_until = 0.0
        self.reset()

    def reset(self) -> None:
        self.recognizer = None
        self.preroll: list[bytes] = []
        self.voiced = self.silent = 0

    def feed(self, block: bytes, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        if now < self.cooldown_until:
            return False
        level = _rms(block)
        speaking = level > max(0.012, self.noise * 3.5)
        if self.recognizer is None:
            if not speaking:
                self.noise = self.noise * 0.95 + min(level, 0.05) * 0.05
                self.preroll = (self.preroll + [block])[-PREROLL_BLOCKS:]
                return False
            self.recognizer = self._vosk.KaldiRecognizer(self.model, RATE, self.grammar)
            for b in self.preroll:
                self.recognizer.AcceptWaveform(b)
            self.voiced = self.silent = 0
        self.recognizer.AcceptWaveform(block)
        self.voiced += 1
        self.silent = 0 if speaking else self.silent + 1
        if self.silent < END_SILENCE_BLOCKS and self.voiced < MAX_UTTERANCE_BLOCKS:
            return False
        text = json.loads(self.recognizer.FinalResult()).get("text", "")
        self.reset()
        if is_wake(text):
            self.cooldown_until = now + COOLDOWN_S
            return True
        return False
