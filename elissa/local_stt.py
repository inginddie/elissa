"""Speech recognition on the user's PC with whisper.cpp: no internet, no API key.

whisper.cpp's Windows build (whisper-server.exe) and a quantized Whisper model are downloaded on demand from pinned
URLs and verified with SHA-256, so the installer stays small. The server runs on a free local port while Elissa
runs; a Windows job object makes sure it never outlives the engine.
"""
import array
import hashlib
import io
import logging
import os
import shutil
import socket
import subprocess
import threading
import time
import wave
import zipfile
from pathlib import Path
from typing import Callable

import httpx

from . import system

log = logging.getLogger(__name__)

SERVER_URL = "https://github.com/ggml-org/whisper.cpp/releases/download/b5454/whisper-bin-x64.zip"
SERVER_SHA256 = "6ba69e3482d7826214f90a6a9c84ca07782aec1e1d0c6a7c30c994fd5d816ccb"
HF = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main"
MODELS = {  # key -> (file, sha256, label)
    "base": ("ggml-base-q5_1.bin", "422f1ae452ade6f30a004d7e5c6a43195e4433bc370bf23fac9cc591f01a8898",
             "rápido · 60 MB"),
    "small": ("ggml-small-q5_1.bin", "ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb",
              "más preciso · 190 MB"),
}


# Whisper always encodes a 30 s window; a ~10 s window (audio context 512) is about 3x faster on a CPU. Longer
# recordings are split at their quietest moment before that limit and transcribed piece by piece.
AUDIO_CTX = 512
CHUNK_MAX_S = 9.5
CHUNK_MIN_S = 5.0


def split_wav(data: bytes) -> list[bytes]:
    """16 kHz mono 16-bit WAV -> WAV pieces of at most CHUNK_MAX_S seconds, cut at low-energy points."""
    with wave.open(io.BytesIO(data)) as w:
        rate, frames = w.getframerate(), w.readframes(w.getnframes())
    samples = array.array("h", frames)
    if len(samples) <= rate * CHUNK_MAX_S:
        return [data]
    hop = rate // 10  # 100 ms

    def energy(at: int) -> int:
        return sum(abs(x) for x in samples[at:at + hop])

    pieces, start = [], 0
    while len(samples) - start > rate * CHUNK_MAX_S:
        lo, hi = start + int(rate * CHUNK_MIN_S), start + int(rate * CHUNK_MAX_S) - hop
        cut = min(range(lo, hi, hop), key=energy) + hop // 2
        pieces.append(samples[start:cut])
        start = cut
    pieces.append(samples[start:])
    out = []
    for piece in pieces:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(piece.tobytes())
        out.append(buf.getvalue())
    return out


def _download(url: str, dest: Path, sha256: str, progress: Callable[[int], None]) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    digest = hashlib.sha256()
    with httpx.stream("GET", url, follow_redirects=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length") or 0)
        done = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_bytes(1 << 17):
                f.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if total:
                    progress(done * 100 // total)
    if digest.hexdigest() != sha256:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"La descarga de {dest.name} no coincide con la esperada; no la usé.")
    tmp.replace(dest)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class LocalWhisper:
    def __init__(self, models_dir: Path, on_status: Callable[[str], None]):
        self.dir = models_dir / "whisper"
        self.on_status = on_status
        self.status = ""
        self.proc: subprocess.Popen | None = None
        self.port = 0
        self.model_key = ""
        self._lock = threading.Lock()
        self._job: system.ChildGuard | None = None

    def _set(self, status: str) -> None:
        self.status = status
        self.on_status(status)

    def server_exe(self) -> Path | None:
        return next(iter(self.dir.glob("**/whisper-server.exe")), None)

    def model_file(self, key: str) -> Path:
        return self.dir / MODELS[key][0]

    def installed(self, key: str) -> bool:
        return bool(self.server_exe()) and self.model_file(key).exists()

    def ensure(self, key: str) -> None:
        """Downloads whatever is missing (server and model), verifying each file."""
        if key not in MODELS:
            raise ValueError(f"Modelo desconocido: {key}")
        self.dir.mkdir(parents=True, exist_ok=True)
        if not self.server_exe():
            zip_path = self.dir / "whisper-bin-x64.zip"
            _download(SERVER_URL, zip_path, SERVER_SHA256, lambda p: self._set(f"descargando el motor {p}%"))
            target = self.dir / "bin"
            shutil.rmtree(target, ignore_errors=True)
            with zipfile.ZipFile(zip_path) as z:
                for member in z.namelist():
                    if member.startswith("/") or ".." in Path(member).parts:
                        raise RuntimeError("El paquete de whisper.cpp no es válido.")
                z.extractall(target)
            zip_path.unlink(missing_ok=True)
        model = self.model_file(key)
        if not model.exists():
            name, sha, _ = MODELS[key]
            _download(f"{HF}/{name}", model, sha, lambda p: self._set(f"descargando el modelo {p}%"))
        self._set("listo")

    def url(self, key: str, threads: int | None = None) -> str:
        """Starts the server (once) with the chosen model and returns its transcription URL."""
        with self._lock:
            if self.proc and self.proc.poll() is None and self.model_key == key:
                return f"http://127.0.0.1:{self.port}/inference"
            self.stop()
            if not self.installed(key):
                self.ensure(key)
            self.port = _free_port()
            threads = threads or max(2, min(8, os.cpu_count() or 4))
            exe = self.server_exe()
            self._set("iniciando")
            self.proc = subprocess.Popen(
                [str(exe), "-m", str(self.model_file(key)), "-l", "es", "-t", str(threads), "-ac", str(AUDIO_CTX),
                 "--host", "127.0.0.1", "--port", str(self.port)],
                cwd=str(exe.parent), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=system.NO_WINDOW)
            try:
                self._job = self._job or system.ChildGuard()
                self._job.add(self.proc)
            except Exception:
                log.warning("could not attach whisper-server to a job object")
            self.model_key = key
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if self.proc.poll() is not None:
                    raise RuntimeError("El reconocimiento local no pudo iniciar.")
                try:
                    with socket.create_connection(("127.0.0.1", self.port), timeout=0.5):
                        break
                except OSError:
                    time.sleep(0.25)
            else:
                self.stop()
                raise RuntimeError("El reconocimiento local tardó demasiado en iniciar.")
            self._set("listo")
            log.info("whisper-server (%s) on port %d", key, self.port)
            return f"http://127.0.0.1:{self.port}/inference"

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None
