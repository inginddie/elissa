"""Local web backend for the desktop shell: setup wizard, agent turns over WebSocket, speech in and out.

Only this launch's shell may talk to it: the shell opens `/?t=<token>`, which sets a SameSite=Strict cookie that every
API call and the WebSocket must carry (so a web page in a browser can't drive the assistant through localhost).
"""
import asyncio
import json
import logging
import os
import re
import secrets
import threading
import time
from pathlib import Path
from contextlib import asynccontextmanager

import edge_tts
import httpx
from fastapi import FastAPI, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from . import __version__, windows_tts, winutil
from .agent import Agent
from .config import (DEFAULTS, HOME, SOUNDS_DIR, STATIC, api_key_name, get_secret, load_settings, save_settings,
                     set_secret)
from .llm import PROVIDERS, LLMError, Provider, build_provider
from .memory import Memory
from .memory import register as register_memory
from .tools import ToolRegistry
from .tools.actions import Actions
from .tools.actions import register as register_actions
from .tools.desktop import Desktop
from .tools.desktop import register as register_desktop
from .tools.file_edit import FileEditor
from .tools.file_edit import register as register_file_edit
from .tools.files import FileTools
from .tools.files import register as register_files
from .tools.mail import MailTools, guess_server
from .tools.mail import register as register_mail
from .tools.mail_send import MailSender
from .tools.mail_send import register as register_mail_send
from .tools.planner import Planner
from .tools.planner import register as register_planner
from .tools.web import register as register_web
from .local_stt import MODELS as LOCAL_MODELS
from .local_stt import LocalWhisper, split_wav
from .wake import WakeListener

log = logging.getLogger("elissa")

TOKEN = os.environ.get("ELISSA_TOKEN") or secrets.token_hex(16)
COOKIE = "elissa_session"
PARENT_PID = int(os.environ.get("ELISSA_PARENT_PID") or 0)
# Browser (dev) mode only: exit when no window has been connected for this long.
IDLE_SHUTDOWN_S = 60
STT_SERVICES = {  # OpenAI-compatible transcription APIs usable with the user's own key
    "openai": ("https://api.openai.com/v1/audio/transcriptions", "gpt-4o-mini-transcribe"),
    "groq": ("https://api.groq.com/openai/v1/audio/transcriptions", "whisper-large-v3-turbo"),
}
MAIL_SECRET = "mail_password"
HALLUCINATIONS = re.compile(r"^(subt[ií]tulos.*|gracias por ver.*|amara\.org.*|\[.*\]|\(.*\)|m[uú]sica|\.+)$", re.I)


def speakable(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "el enlace", text)
    text = re.sub(r"^\s*([-*•]|\d+\.)\s+", "", text, flags=re.M)
    text = re.sub(r"[*_#`>|]", "", text)
    return re.sub(r"\s+", " ", text).strip()


class SentenceSplitter:
    """Accumulates streamed text and yields speakable chunks as sentences complete."""
    BOUNDARY = re.compile(r"(?<=[.!?…:;])\s+|\n+")

    def __init__(self, min_len: int = 30):
        self.buf, self.min_len = "", min_len

    def feed(self, text: str) -> list[str]:
        self.buf += text
        parts = self.BOUNDARY.split(self.buf)
        self.buf = parts.pop()
        out, cur = [], ""
        for p in parts:
            cur = f"{cur} {p}".strip()
            if len(cur) >= self.min_len:
                out.append(cur)
                cur = ""
        if cur:
            self.buf = f"{cur} {self.buf}".strip()
        return [s for s in map(speakable, out) if s]

    def flush(self) -> list[str]:
        rest, self.buf = speakable(self.buf), ""
        return [rest] if rest else []


class Hub:
    def __init__(self):
        self.clients: set[WebSocket] = set()
        self.ever_connected = False
        self.last_left = time.time()

    async def broadcast(self, msg: dict) -> None:
        data = json.dumps(msg, ensure_ascii=False)
        for ws in list(self.clients):
            try:
                await ws.send_text(data)
            except Exception:
                self.clients.discard(ws)


class Brain:
    """Owns settings, provider, tools, memory and the agent; runs one user turn at a time."""

    def __init__(self, hub: Hub):
        self.hub = hub
        self.settings = load_settings()
        self._provider: Provider | None = None
        self._provider_key = None
        self.memory = Memory(self.provider_or_none)
        self.tools = ToolRegistry()
        self.tools.approver = self.request_approval
        self.approvals: dict[str, asyncio.Future] = {}
        self.planner = Planner(HOME)
        self.handed_over: set[str] = set()  # files dropped on Elissa during this conversation
        self.desktop = Desktop(lambda: {os.getpid(), PARENT_PID})
        self.loop: asyncio.AbstractEventLoop | None = None
        self.wake = WakeListener(HOME / "models", self._on_wake, self._on_wake_status)
        self.local_stt = LocalWhisper(HOME / "models",
                                      lambda status: self._from_thread({"type": "stt_local_status", "status": status}))
        self.rebuild_tools()
        self.agent = Agent(lambda: self.settings, self.provider, self.tools, self.budget)
        self.turn = 0
        self.task: asyncio.Task | None = None
        self.splitter = SentenceSplitter()
        self.reply = ""

    # ----- configuration -----

    def configured(self) -> bool:
        p = self.settings.get("provider")
        return bool(p in PROVIDERS and (not PROVIDERS[p]["needs_key"] or get_secret(api_key_name(p))))

    def provider(self) -> Provider:
        s = self.settings
        if not s.get("provider"):
            raise LLMError("Aún no has elegido un proveedor de IA. Abre Ajustes para configurarlo.")
        key = (s["provider"], s.get("model"), s.get("base_url"), get_secret(api_key_name(s["provider"])))
        if self._provider is None or key != self._provider_key:
            self._provider = build_provider(s["provider"], s.get("model", ""), s.get("base_url", ""))
            self._provider_key = key
        return self._provider

    def provider_or_none(self) -> Provider | None:
        try:
            return self.provider()
        except LLMError:
            return None

    def budget(self) -> int:
        # The provider preset caps the budget (small local models have small context windows).
        preset = PROVIDERS.get(self.settings.get("provider"), {}).get("budget", 20000)
        return min(int(self.settings.get("context_budget") or preset), preset)

    def rebuild_tools(self) -> None:
        reg = self.tools
        reg.clear()  # same registry object: the agent keeps its reference
        files = FileTools(lambda: self.settings.get("allowed_folders") or [os.path.expanduser("~")],
                          lambda: self.handed_over)
        register_files(reg, files)
        register_actions(reg, Actions(files))
        register_file_edit(reg, FileEditor(files))
        register_planner(reg, self.planner)
        if self.settings.get("computer_use", True):
            register_desktop(reg, self.desktop)
        register_web(reg)
        register_memory(reg, self.memory)
        if self.settings.get("mail_enabled"):
            register_mail(reg, MailTools(lambda: self.settings, lambda: get_secret(MAIL_SECRET)))
            if self.settings.get("mail_send"):
                register_mail_send(reg, MailSender(lambda: self.settings, lambda: get_secret(MAIL_SECRET), files))

    def status(self) -> dict:
        return {"type": "status", "ready": self.configured(), "configured": self.configured(),
                "busy": bool(self.task and not self.task.done()), "turn": self.turn}

    # ----- conversation -----

    async def ask(self, text: str) -> None:
        await self.interrupt()
        if self.memory.idle_expired():
            self.new_conversation()
        self.memory.record("user", text)
        self.turn += 1
        self.splitter, self.reply = SentenceSplitter(), ""
        await self.hub.broadcast({"type": "turn", "turn": self.turn, "text": text})
        self.task = asyncio.create_task(self._run(text, self.turn))

    async def _run(self, text: str, turn: int) -> None:
        async def emit(ev: dict) -> None:
            kind = ev["type"]
            if kind == "delta":
                self.reply += ev["text"]
                await self.hub.broadcast({"type": "delta", "turn": turn, "text": ev["text"]})
                for s in self.splitter.feed(ev["text"]):
                    await self.hub.broadcast({"type": "say", "turn": turn, "text": s})
            elif kind == "block_end":
                for s in self.splitter.flush():
                    await self.hub.broadcast({"type": "say", "turn": turn, "text": s})
                self.reply += "\n"
                await self.hub.broadcast({"type": "delta", "turn": turn, "text": "\n"})
            elif kind == "tool":
                await self.hub.broadcast({"type": "tool", "turn": turn, "name": ev["name"]})

        started = time.monotonic()
        log.info("turn %d started", turn)
        try:
            reply = await self.agent.run_turn(text, emit)
            self.memory.record("assistant", reply)
            log.info("turn %d done in %.1fs", turn, time.monotonic() - started)
        except asyncio.CancelledError:
            log.info("turn %d interrupted after %.1fs", turn, time.monotonic() - started)
            return
        except LLMError as e:
            log.warning("turn %d failed: %s", turn, e)
            await self.hub.broadcast({"type": "error", "turn": turn, "message": str(e)})
        except Exception as e:
            log.exception("turn failed")
            await self.hub.broadcast({"type": "error", "turn": turn, "message": f"Algo falló: {e}"})
        await self.hub.broadcast({"type": "done", "turn": turn})

    async def interrupt(self) -> None:
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except BaseException:
                pass
            if self.reply.strip():
                self.memory.record("assistant", self.reply.strip() + " …(interrumpido)")
            self.turn += 1

    def new_conversation(self) -> None:
        self.memory.close()
        self.agent.reset()
        self.handed_over.clear()

    def hand_over(self, paths: list[str]) -> list[str]:
        """Files the user dropped on the window; returns the full paths accepted."""
        accepted = []
        for raw in paths[:10]:
            p = Path(str(raw)).resolve()
            if p.is_file():
                self.handed_over.add(str(p).lower())
                accepted.append(str(p))
        return accepted

    # ----- wake phrase (runs in its own thread) -----

    def _from_thread(self, msg: dict) -> None:
        if self.loop:
            asyncio.run_coroutine_threadsafe(self.hub.broadcast(msg), self.loop)

    def _on_wake(self) -> None:
        self._from_thread({"type": "wake"})

    def _on_wake_status(self, status: str) -> None:
        self._from_thread({"type": "wake_status", "status": status})

    # ----- approvals -----

    async def request_approval(self, tool: str, card: dict) -> bool:
        """Shows an approval card in the window and waits for the user's click. No window: denied."""
        if not self.hub.clients:
            return False
        approval_id = secrets.token_hex(8)  # unguessable: only the window that shows the card can answer it
        future = asyncio.get_running_loop().create_future()
        self.approvals[approval_id] = future
        log.info("approval %s requested for %s", approval_id, tool)
        await self.hub.broadcast({"type": "approval", "id": approval_id, "turn": self.turn, "tool": tool, **card})
        try:
            return await future
        finally:
            self.approvals.pop(approval_id, None)
            await self.hub.broadcast({"type": "approval_done", "id": approval_id})

    def answer_approval(self, approval_id: str, approved: bool) -> None:
        future = self.approvals.get(approval_id)
        if future and not future.done():
            future.set_result(approved)

    def deny_all_approvals(self) -> None:
        for future in self.approvals.values():
            if not future.done():
                future.set_result(False)


hub = Hub()
state: dict = {}


async def stop_engine(reason: str) -> None:
    log.info("%s; saving memory and exiting", reason)
    brain: Brain = state["brain"]
    await brain.interrupt()
    task = brain.memory.close()
    if task:
        try:
            await asyncio.wait_for(task, 120)
        except Exception:
            log.exception("memory consolidation failed on exit")
    os._exit(0)


def watch_parent(loop: asyncio.AbstractEventLoop) -> None:
    """The engine lives as long as the desktop shell that started it, even if the shell crashes."""
    def wait():
        winutil.wait_for_exit(PARENT_PID)
        asyncio.run_coroutine_threadsafe(stop_engine("desktop shell exited"), loop)
    threading.Thread(target=wait, daemon=True).start()


async def reminder_loop() -> None:
    """Fires due reminders and timers: the window speaks them and shows a Windows notification."""
    brain: Brain = state["brain"]
    while True:
        try:
            # only with a window connected, so a reminder that comes due during startup isn't lost
            for item in (await asyncio.to_thread(brain.planner.pop_due) if hub.clients else []):
                log.info("reminder %s fired", item["id"])
                await hub.broadcast({"type": "reminder", **item})
        except Exception:
            log.exception("reminder loop")
        await asyncio.sleep(2)


async def watchdog() -> None:
    while True:
        await asyncio.sleep(5)
        brain: Brain = state["brain"]
        if (not PARENT_PID and hub.ever_connected and not hub.clients
                and time.time() - hub.last_left > IDLE_SHUTDOWN_S):
            await stop_engine("browser window closed")
        if brain.memory.idle_expired() and not (brain.task and not brain.task.done()):
            brain.new_conversation()


@asynccontextmanager
async def lifespan(app: FastAPI):
    brain = Brain(hub)
    state["brain"] = brain
    brain.loop = asyncio.get_running_loop()
    brain.wake.set_enabled(bool(brain.settings.get("wake_word")))
    if brain.settings.get("stt") == "local":
        prepare_local_stt(brain)  # warm up, so the first sentence isn't slow
    tasks = [asyncio.create_task(watchdog()), asyncio.create_task(brain.memory.recover()),
             asyncio.create_task(reminder_loop())]
    if PARENT_PID:
        watch_parent(asyncio.get_running_loop())
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def authorized(cookies) -> bool:
    return secrets.compare_digest(cookies.get(COOKIE, ""), TOKEN)


@app.middleware("http")
async def guard(request: Request, call_next):
    if request.url.path.startswith("/api/") and not authorized(request.cookies):
        return JSONResponse({"error": "No autorizado"}, 403)
    resp = await call_next(request)
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/")
async def index(request: Request, t: str = ""):
    if t and secrets.compare_digest(t, TOKEN):
        resp = FileResponse(STATIC / "index.html")
        resp.set_cookie(COOKIE, TOKEN, httponly=True, samesite="strict")
        return resp
    if authorized(request.cookies):
        return FileResponse(STATIC / "index.html")
    return PlainTextResponse("Abre Elissa desde su acceso directo.", 403)


# ----- voice -----

WINDOWS_VOICE = "windows:"  # voice ids for the offline Windows voices
EDGE_TIMEOUT_S = 12


async def _edge_tts(text: str, voice: str, speed: float) -> bytes:
    rate = f"{round((speed - 1) * 100):+d}%"
    audio = bytearray()
    async for chunk in edge_tts.Communicate(text, voice, rate=rate).stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
    if not audio:
        raise RuntimeError("Edge TTS returned no audio")
    return bytes(audio)


@app.get("/api/tts")
async def tts(text: str):
    """Speech for a sentence: the chosen Edge voice, or a Windows voice (offline). If Edge can't be reached, the
    Windows voice answers instead of leaving Elissa mute."""
    s = state["brain"].settings
    voice, speed = s.get("voice", ""), float(s.get("speed", 1.0))
    if not voice.startswith(WINDOWS_VOICE):
        try:
            audio = await asyncio.wait_for(_edge_tts(text, voice, speed), EDGE_TIMEOUT_S)
            return Response(audio, media_type="audio/mpeg")
        except Exception as e:
            log.warning("Edge voice failed (%s); using the Windows voice", e)
            voice = ""
    wav = await asyncio.to_thread(windows_tts.synthesize, text, voice.removeprefix(WINDOWS_VOICE), speed)
    return Response(wav, media_type="audio/wav")


@app.get("/api/voices")
async def voices():
    lang = state["brain"].settings.get("language", "es-CO")[:2]
    out = []
    try:
        found = await asyncio.wait_for(edge_tts.list_voices(), EDGE_TIMEOUT_S)
        out = sorted(({"id": v["ShortName"], "label": f"{v['ShortName'].split('-')[-1].replace('Neural', '')} "
                       f"({v['Locale']}, {'mujer' if v['Gender'] == 'Female' else 'hombre'})"}
                      for v in found if v["Locale"].startswith(lang)), key=lambda v: v["id"])
    except Exception as e:
        log.warning("could not list Edge voices: %s", e)
    try:
        for v in await asyncio.to_thread(windows_tts.list_voices):
            spanish = v["lang"].upper() in windows_tts.SPANISH
            if spanish or lang != "es":
                short = v["name"].replace("Microsoft ", "").replace(" Desktop", "")
                out.append({"id": WINDOWS_VOICE + v["name"], "label": f"{short} · Windows, sin conexión"})
    except Exception as e:
        log.warning("could not list Windows voices: %s", e)
    return out


MIN_AUDIO_BYTES = 1500
WEBM_MAGIC = bytes.fromhex("1a45dfa3")  # EBML header every WebM recording starts with


async def transcribe_locally(audio: bytes, s: dict):
    if len(audio) < MIN_AUDIO_BYTES:
        return {"text": ""}
    if not audio.startswith(b"RIFF"):
        return JSONResponse({"error": "No pude procesar el audio; intenta de nuevo."}, 422)
    brain: Brain = state["brain"]
    try:
        url = await asyncio.to_thread(brain.local_stt.url, s.get("stt_local_model", "base"))
        texts = []
        async with httpx.AsyncClient(timeout=120) as client:
            for piece in await asyncio.to_thread(split_wav, audio):
                r = await client.post(url, data={"response_format": "json", "language": s.get("language", "es")[:2]},
                                      files={"file": ("audio.wav", piece, "audio/wav")})
                r.raise_for_status()
                texts.append(r.json().get("text", "").strip())
    except Exception as e:
        log.warning("local stt failed: %s", e)
        return JSONResponse({"error": f"El reconocimiento local falló: {e}"}, 502)
    text = " ".join(t for t in texts if t).strip()
    return {"text": "" if HALLUCINATIONS.match(text) or len(text) < 2 else text}


def stt_error_message(status: int, body: str) -> str:
    if status in (401, 403):
        return "La API key de voz no es válida; revísala en Ajustes → Voz."
    if status == 429:
        return "El servicio de voz está saturado o llegaste al límite; intenta en un momento."
    if "media" in body or "audio" in body:
        return "No pude procesar el audio; intenta de nuevo."
    return f"El servicio de voz falló ({status}); intenta de nuevo."


def stt_service(s: dict) -> str | None:
    """Which transcription service to use: the chosen one, or in auto mode the chat provider's (if it has one),
    then any cloud key already stored, then the user's own endpoint."""
    mode = s.get("stt", "auto")
    if mode != "auto":
        return mode
    for name in [s.get("provider")] + list(STT_SERVICES):
        if name in STT_SERVICES and get_secret(api_key_name(name)):
            return name
    if s.get("stt_url"):
        return "endpoint"
    brain = state.get("brain")
    if brain and brain.local_stt.installed(s.get("stt_local_model", "base")):
        return "local"
    return None


def prepare_local_stt(brain: "Brain") -> None:
    """Downloads (if needed) and starts local recognition in the background, reporting progress to the window."""
    key = brain.settings.get("stt_local_model", "base")

    def work():
        try:
            brain.local_stt.url(key)
        except Exception as e:
            log.warning("local speech recognition unavailable: %s", e)
            brain._from_thread({"type": "stt_local_status", "status": f"error: {e}"})
    threading.Thread(target=work, name="local-stt", daemon=True).start()


@app.get("/api/stt/status")
async def stt_status():
    brain: Brain = state["brain"]
    key = brain.settings.get("stt_local_model", "base")
    return {"service": stt_service(brain.settings),
            "local": {"installed": brain.local_stt.installed(key), "status": brain.local_stt.status,
                      "models": {k: v[2] for k, v in LOCAL_MODELS.items()}}}


@app.post("/api/stt")
async def stt(file: UploadFile):
    s = state["brain"].settings
    service = stt_service(s)
    if service == "local":
        return await transcribe_locally(await file.read(), s)
    data = {"response_format": "json", "language": s.get("language", "es")[:2]}
    headers = {}
    if service in STT_SERVICES:
        url, model = STT_SERVICES[service]
        key = get_secret(api_key_name(service))
        if not key:
            return JSONResponse({"error": f"Falta la API key de {PROVIDERS[service]['label']} para la voz"}, 400)
        data["model"] = model
        headers["Authorization"] = f"Bearer {key}"
    elif service == "endpoint" and s.get("stt_url"):
        url = s["stt_url"]
    else:
        return JSONResponse({"error": "Configura el reconocimiento de voz en Ajustes → Voz"}, 400)
    audio = await file.read()
    if len(audio) < MIN_AUDIO_BYTES:  # a click or an empty recording: nothing to transcribe
        log.info("stt skipped: %d bytes of audio", len(audio))
        return {"text": ""}
    if not audio.startswith(WEBM_MAGIC):  # a recording without its header can't be decoded by any service
        log.warning("stt skipped: corrupt recording (%d bytes, no WebM header)", len(audio))
        return JSONResponse({"error": "No pude procesar el audio; intenta de nuevo."}, 422)
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, headers=headers, data=data, files={"file": ("audio.webm", audio, "audio/webm")})
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        log.warning("stt %s failed (%d bytes): %s %s", service, len(audio), e.response.status_code,
                    e.response.text[:300])
        return JSONResponse({"error": stt_error_message(e.response.status_code, e.response.text)}, 502)
    except httpx.HTTPError as e:
        return JSONResponse({"error": f"No pude conectar con el servicio de voz: {e}"}, 502)
    text = r.json().get("text", "").strip()
    return {"text": "" if HALLUCINATIONS.match(text) or len(text) < 2 else text}


# ----- sounds -----

SOUND_EXT = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".m4a": "audio/mp4"}


@app.get("/api/sounds")
async def custom_sounds():
    """The user's replacement sounds: files named like a built-in sound (listen.wav, done.mp3…)."""
    if not SOUNDS_DIR.is_dir():
        return []
    return [{"name": f.stem.lower(), "url": f"/api/sounds/{f.name}"}
            for f in sorted(SOUNDS_DIR.iterdir()) if f.is_file() and f.suffix.lower() in SOUND_EXT]


@app.get("/api/sounds/{filename}")
async def custom_sound(filename: str):
    path = (SOUNDS_DIR / filename).resolve()
    if path.parent != SOUNDS_DIR.resolve() or path.suffix.lower() not in SOUND_EXT or not path.is_file():
        return JSONResponse({"error": "No existe"}, 404)
    return FileResponse(path, media_type=SOUND_EXT[path.suffix.lower()])


@app.post("/api/sounds/open-folder")
async def open_sounds_folder():
    SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
    os.startfile(SOUNDS_DIR)
    return {"ok": True, "path": str(SOUNDS_DIR)}


# ----- settings & setup wizard -----

@app.get("/api/settings")
async def get_settings():
    return state["brain"].settings


@app.post("/api/settings")
async def set_settings(changes: dict):
    brain: Brain = state["brain"]
    changes = {k: v for k, v in changes.items() if k in DEFAULTS and k not in ("provider", "model", "base_url")}
    brain.settings.update(changes)
    save_settings(brain.settings)
    if {"allowed_folders", "mail_enabled", "mail_send", "computer_use"} & changes.keys():
        brain.rebuild_tools()
    if "wake_word" in changes:
        brain.wake.set_enabled(bool(brain.settings["wake_word"]))
    if brain.settings.get("stt") == "local" and {"stt", "stt_local_model"} & changes.keys():
        prepare_local_stt(brain)
    await hub.broadcast({"type": "settings", "settings": brain.settings})
    return brain.settings


@app.get("/api/providers")
async def providers():
    s = state["brain"].settings
    return {"current": {"provider": s.get("provider"), "model": s.get("model"), "base_url": s.get("base_url")},
            "providers": [{"id": k, **{f: v[f] for f in ("label", "needs_key", "suggested", "key_url")},
                           "has_key": bool(get_secret(api_key_name(k)))} for k, v in PROVIDERS.items()]}


@app.post("/api/providers/test")
async def test_provider(body: dict):
    """List models with the given (or stored) key; the wizard calls this before saving."""
    pid = body.get("provider", "")
    key = body.get("api_key") or None
    try:
        provider = build_provider(pid, body.get("model", ""), body.get("base_url", ""), key)
        models = await asyncio.wait_for(provider.list_models(), 20)
    except (LLMError, asyncio.TimeoutError) as e:
        return JSONResponse({"ok": False, "error": str(e) or "El proveedor no respondió."}, 400)
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"No pude conectar: {e}"}, 400)
    return {"ok": True, "models": models}


@app.post("/api/providers/save")
async def save_provider(body: dict):
    brain: Brain = state["brain"]
    pid = body.get("provider", "")
    if pid not in PROVIDERS:
        return JSONResponse({"error": "Proveedor desconocido"}, 400)
    if body.get("api_key"):
        set_secret(api_key_name(pid), body["api_key"].strip())
    brain.settings.update(provider=pid, model=body.get("model", "") or PROVIDERS[pid]["suggested"],
                          base_url=body.get("base_url", ""))
    save_settings(brain.settings)
    try:
        reply = await asyncio.wait_for(brain.provider().complete("Responde en una sola palabra.", "Di: listo"), 60)
    except (LLMError, asyncio.TimeoutError) as e:
        return JSONResponse({"ok": False, "error": str(e) or "El modelo no respondió a tiempo."}, 400)
    await hub.broadcast(brain.status())
    await hub.broadcast({"type": "settings", "settings": brain.settings})
    return {"ok": True, "reply": reply.strip()[:80]}


@app.post("/api/keys")
async def save_key(body: dict):
    """Stores a provider key without switching the chat provider (e.g. a Groq key just for speech)."""
    pid = body.get("provider", "")
    if pid not in PROVIDERS or not PROVIDERS[pid]["needs_key"]:
        return JSONResponse({"error": "Proveedor desconocido"}, 400)
    set_secret(api_key_name(pid), body.get("api_key", "").strip())
    return {"ok": True, "has_key": bool(get_secret(api_key_name(pid)))}


@app.post("/api/mail/save")
async def save_mail(body: dict):
    brain: Brain = state["brain"]
    user = body.get("user", "").strip()
    if body.get("password"):
        set_secret(MAIL_SECRET, body["password"].replace(" ", ""))
    brain.settings.update(mail_enabled=bool(body.get("enabled")), mail_user=user,
                          mail_server=body.get("server", "").strip() or (guess_server(user) if user else ""))
    save_settings(brain.settings)
    brain.rebuild_tools()
    if not brain.settings["mail_enabled"]:
        return {"ok": True, "status": "Correo desactivado"}
    try:
        status = await asyncio.to_thread(MailTools(lambda: brain.settings, lambda: get_secret(MAIL_SECRET)).test)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, 400)
    return {"ok": True, "status": status, "server": brain.settings["mail_server"]}


@app.post("/api/pick-folder")
async def pick_folder():
    return {"path": await asyncio.to_thread(winutil.pick_folder, os.path.expanduser("~"))}


@app.post("/api/quit")
async def quit_engine():
    """The shell asks the engine to save the conversation and exit (on quit, or before installing an update)."""
    asyncio.get_running_loop().call_later(0.2, lambda: asyncio.create_task(stop_engine("asked to quit")))
    return {"ok": True}


@app.get("/api/health")
async def health():
    brain: Brain = state["brain"]
    return {"version": __version__, "configured": brain.configured(), "provider": brain.settings.get("provider"),
            "model": brain.settings.get("model"), "mail": brain.settings.get("mail_enabled"),
            "clients": len(hub.clients)}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    origin = ws.headers.get("origin", "")
    if not authorized(ws.cookies) or (origin and not origin.startswith("http://127.0.0.1:")):
        await ws.close(code=4403)
        return
    await ws.accept()
    hub.clients.add(ws)
    hub.ever_connected = True
    brain: Brain = state["brain"]
    await ws.send_text(json.dumps({"type": "settings", "settings": brain.settings}, ensure_ascii=False))
    await ws.send_text(json.dumps(brain.status()))
    await ws.send_text(json.dumps({"type": "wake_status", "status": brain.wake.status}, ensure_ascii=False))
    try:
        while True:
            msg = json.loads(await ws.receive_text())
            kind = msg.get("type")
            if kind == "text" and msg.get("text", "").strip():
                await brain.ask(msg["text"].strip())
            elif kind == "interrupt":
                log.info("interrupt requested by the window")
                await brain.interrupt()
            elif kind == "ui_state":
                # the wake phrase pauses while Elissa herself listens or speaks
                brain.wake.busy = msg.get("state") in ("listening", "transcribing", "speaking")
            elif kind == "client_error":
                log.warning("window error: %s", str(msg.get("message", ""))[:500])
            elif kind == "attach":
                accepted = brain.hand_over(list(msg.get("paths") or []))
                log.info("%d file(s) handed over", len(accepted))
                await ws.send_text(json.dumps({"type": "attached", "paths": accepted}, ensure_ascii=False))
            elif kind == "approval_reply":
                brain.answer_approval(str(msg.get("id", "")), msg.get("approved") is True)
            elif kind == "reset":
                await brain.interrupt()
                brain.new_conversation()
    except WebSocketDisconnect:
        pass
    finally:
        hub.clients.discard(ws)
        hub.last_left = time.time()
        if not hub.clients:
            brain.deny_all_approvals()  # nobody left to see the card
